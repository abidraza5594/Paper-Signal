from __future__ import annotations

import os
import re
import uuid
from pathlib import Path

from fastapi import UploadFile


class UploadValidationError(ValueError):
    pass


class LocalStorage:
    chunk_size = 1024 * 1024

    def __init__(self, upload_dir: Path, max_upload_bytes: int):
        self.upload_dir = upload_dir
        self.max_upload_bytes = max_upload_bytes
        self.upload_dir.mkdir(parents=True, exist_ok=True)

    async def save_pdf(self, upload: UploadFile) -> tuple[Path, int, str]:
        original_name = self._safe_name(upload.filename or "document.pdf")
        destination = self.upload_dir / f"{uuid.uuid4().hex}.pdf"
        total = 0
        signature = bytearray()

        try:
            with destination.open("wb") as output:
                while True:
                    chunk = await upload.read(self.chunk_size)
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
            if total == 0:
                raise UploadValidationError("The uploaded file is empty.")
            if bytes(signature) != b"%PDF-":
                raise UploadValidationError("The uploaded file is not a valid PDF.")
            return destination, total, original_name
        except Exception:
            destination.unlink(missing_ok=True)
            raise
        finally:
            await upload.close()

    @staticmethod
    def delete(path: str | Path) -> None:
        Path(path).unlink(missing_ok=True)

    @staticmethod
    def _safe_name(name: str) -> str:
        base = os.path.basename(name).strip() or "document.pdf"
        base = re.sub(r"[^A-Za-z0-9._() -]", "_", base)[:180]
        if not base.lower().endswith(".pdf"):
            base += ".pdf"
        return base

