"""Where uploaded PDFs live.

Two implementations behind one interface. Local disk is right for a single
machine; S3 is what a container platform needs, because containers are replaced
without warning and anything on their own disk goes with them.

Both hand back an opaque reference string that is stored on the job. Callers
never build paths themselves; they ask for `local_copy` when they need bytes.
"""

from __future__ import annotations

import os
import re
import tempfile
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator, Protocol

from fastapi import UploadFile


class UploadValidationError(ValueError):
    pass


CHUNK_SIZE = 1024 * 1024
PDF_SIGNATURE = b"%PDF-"


def safe_name(name: str) -> str:
    base = os.path.basename(name).strip() or "document.pdf"
    base = re.sub(r"[^A-Za-z0-9._() -]", "_", base)[:180]
    if not base.lower().endswith(".pdf"):
        base += ".pdf"
    return base


def _check(total: int, signature: bytes, max_bytes: int) -> None:
    if total == 0:
        raise UploadValidationError("The uploaded file is empty.")
    if signature != PDF_SIGNATURE:
        raise UploadValidationError("The uploaded file is not a valid PDF.")
    if total > max_bytes:
        raise UploadValidationError(f"PDF exceeds the {max_bytes // (1024 * 1024)} MB limit.")


class Storage(Protocol):
    async def save_pdf(self, upload: UploadFile) -> tuple[str, int, str]: ...
    def delete(self, reference: str) -> None: ...
    def local_copy(self, reference: str) -> Iterator[Path]: ...


class LocalStorage:
    """Files on this machine's disk."""

    def __init__(self, upload_dir: Path, max_upload_bytes: int):
        self.upload_dir = Path(upload_dir)
        self.max_upload_bytes = max_upload_bytes
        self.upload_dir.mkdir(parents=True, exist_ok=True)

    async def save_pdf(self, upload: UploadFile) -> tuple[str, int, str]:
        original_name = safe_name(upload.filename or "document.pdf")
        destination = self.upload_dir / f"{uuid.uuid4().hex}.pdf"
        total = 0
        signature = bytearray()
        try:
            with destination.open("wb") as output:
                while True:
                    chunk = await upload.read(CHUNK_SIZE)
                    if not chunk:
                        break
                    total += len(chunk)
                    if total > self.max_upload_bytes:
                        raise UploadValidationError(
                            f"PDF exceeds the {self.max_upload_bytes // (1024 * 1024)} MB limit."
                        )
                    if len(signature) < 5:
                        signature.extend(chunk[: 5 - len(signature)])
                    output.write(chunk)
            _check(total, bytes(signature), self.max_upload_bytes)
            return str(destination), total, original_name
        except Exception:
            destination.unlink(missing_ok=True)
            raise
        finally:
            await upload.close()

    def delete(self, reference: str) -> None:
        Path(reference).unlink(missing_ok=True)

    @contextmanager
    def local_copy(self, reference: str) -> Iterator[Path]:
        yield Path(reference)


class S3Storage:
    """Files in an S3 bucket. The reference is the object key.

    Uploads stream straight into S3, so a large PDF never sits in memory.
    """

    def __init__(self, bucket: str, max_upload_bytes: int, prefix: str = "uploads/"):
        import boto3  # imported here so local runs do not need it

        self.bucket = bucket
        self.prefix = prefix.strip("/") + "/" if prefix else ""
        self.max_upload_bytes = max_upload_bytes
        self.client = boto3.client("s3")

    async def save_pdf(self, upload: UploadFile) -> tuple[str, int, str]:
        from boto3.s3.transfer import TransferConfig

        original_name = safe_name(upload.filename or "document.pdf")
        key = f"{self.prefix}{uuid.uuid4().hex}.pdf"

        # Buffer to a temp file first: size and signature must be validated before
        # anything is stored, and S3 cannot be asked to undo a bad upload.
        handle = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
        temp_path = Path(handle.name)
        total = 0
        signature = bytearray()
        try:
            try:
                while True:
                    chunk = await upload.read(CHUNK_SIZE)
                    if not chunk:
                        break
                    total += len(chunk)
                    if total > self.max_upload_bytes:
                        raise UploadValidationError(
                            f"PDF exceeds the {self.max_upload_bytes // (1024 * 1024)} MB limit."
                        )
                    if len(signature) < 5:
                        signature.extend(chunk[: 5 - len(signature)])
                    handle.write(chunk)
            finally:
                # Close before any cleanup: Windows refuses to delete an open file.
                handle.close()
                await upload.close()
            _check(total, bytes(signature), self.max_upload_bytes)
        except Exception:
            temp_path.unlink(missing_ok=True)
            raise

        try:
            self.client.upload_file(
                str(temp_path), self.bucket, key,
                ExtraArgs={"ContentType": "application/pdf"},
                Config=TransferConfig(multipart_threshold=16 * 1024 * 1024),
            )
        finally:
            temp_path.unlink(missing_ok=True)
        return key, total, original_name

    def delete(self, reference: str) -> None:
        try:
            self.client.delete_object(Bucket=self.bucket, Key=reference)
        except Exception:
            # Deleting an object that is already gone is not a failure.
            pass

    @contextmanager
    def local_copy(self, reference: str) -> Iterator[Path]:
        """Download to a temp file so PyMuPDF can read it, then clean up."""
        handle = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
        handle.close()
        path = Path(handle.name)
        try:
            self.client.download_file(self.bucket, reference, str(path))
            yield path
        finally:
            path.unlink(missing_ok=True)


def build_storage(settings) -> Storage:
    """S3 when a bucket is configured, local disk otherwise."""
    if settings.uploads_bucket:
        return S3Storage(settings.uploads_bucket, settings.max_upload_bytes)
    return LocalStorage(settings.upload_dir, settings.max_upload_bytes)
