from io import BytesIO
from pathlib import Path

import pytest
from starlette.datastructures import UploadFile

from app.storage import LocalStorage, S3Storage, UploadValidationError
import fitz


@pytest.mark.asyncio
async def test_streamed_pdf_upload_is_saved(tmp_path):
    storage = LocalStorage(tmp_path, max_upload_bytes=1024)
    upload = UploadFile(filename="sample.pdf", file=BytesIO(b"%PDF-1.4\nhello"))

    reference, size, name = await storage.save_pdf(upload)

    # The reference is opaque: callers ask the storage for the bytes.
    assert Path(reference).exists()
    assert size == 14
    assert name == "sample.pdf"
    with storage.local_copy(reference) as local:
        assert local.read_bytes().startswith(b"%PDF-")


@pytest.mark.asyncio
async def test_upload_rejects_non_pdf(tmp_path):
    storage = LocalStorage(tmp_path, max_upload_bytes=1024)
    upload = UploadFile(filename="fake.pdf", file=BytesIO(b"hello"))

    with pytest.raises(UploadValidationError, match="not a valid PDF"):
        await storage.save_pdf(upload)


@pytest.mark.asyncio
async def test_upload_enforces_size_limit_and_cleans_partial(tmp_path):
    storage = LocalStorage(tmp_path, max_upload_bytes=8)
    upload = UploadFile(filename="large.pdf", file=BytesIO(b"%PDF-123456789"))

    with pytest.raises(UploadValidationError, match="exceeds"):
        await storage.save_pdf(upload)

    assert list(tmp_path.iterdir()) == []



class FakeS3:
    """Just enough of the S3 client to prove the storage contract."""

    def __init__(self):
        self.objects = {}

    def upload_file(self, filename, bucket, key, **_kwargs):
        self.objects[(bucket, key)] = Path(filename).read_bytes()

    def download_file(self, bucket, key, filename):
        Path(filename).write_bytes(self.objects[(bucket, key)])

    def delete_object(self, Bucket, Key):
        self.objects.pop((Bucket, Key), None)


def s3_storage(max_bytes=1024):
    storage = S3Storage.__new__(S3Storage)
    storage.bucket = "test-bucket"
    storage.prefix = "uploads/"
    storage.max_upload_bytes = max_bytes
    storage.client = FakeS3()
    return storage


@pytest.mark.asyncio
async def test_s3_upload_stores_and_reads_back():
    storage = s3_storage()
    upload = UploadFile(filename="sample.pdf", file=BytesIO(b"%PDF-1.4\nhello"))

    key, size, name = await storage.save_pdf(upload)

    assert key.startswith("uploads/") and key.endswith(".pdf")
    assert size == 14 and name == "sample.pdf"

    # A worker on another machine can fetch the same object.
    with storage.local_copy(key) as local:
        assert local.read_bytes() == b"%PDF-1.4\nhello"
        temp = local
    assert not temp.exists(), "the downloaded copy must not be left behind"

    storage.delete(key)
    assert storage.client.objects == {}


@pytest.mark.asyncio
async def test_s3_rejects_bad_uploads_without_storing_anything():
    storage = s3_storage()
    with pytest.raises(UploadValidationError, match="not a valid PDF"):
        await storage.save_pdf(UploadFile(filename="fake.pdf", file=BytesIO(b"hello")))
    assert storage.client.objects == {}

    small = s3_storage(max_bytes=8)
    with pytest.raises(UploadValidationError, match="exceeds"):
        await small.save_pdf(UploadFile(filename="big.pdf", file=BytesIO(b"%PDF-123456789")))
    assert small.client.objects == {}, "a rejected upload must never reach the bucket"


@pytest.mark.asyncio
async def test_deleting_a_missing_object_is_not_an_error():
    storage = s3_storage()

    class Broken(FakeS3):
        def delete_object(self, **_kwargs):
            raise RuntimeError("NoSuchKey")

    storage.client = Broken()
    storage.delete("uploads/gone.pdf")  # must not raise


@pytest.mark.asyncio
@pytest.mark.parametrize("remote", [False, True])
async def test_image_uploads_are_canonicalized_for_the_same_pipeline(tmp_path, remote):
    document = fitz.open()
    page = document.new_page(width=200, height=100)
    page.insert_text((20, 40), "Reference Q7")
    image = page.get_pixmap().tobytes("png")
    document.close()
    storage = s3_storage(max_bytes=100_000) if remote else LocalStorage(tmp_path, 100_000)
    reference, size, name = await storage.save_pdf(UploadFile(filename="scan.png", file=BytesIO(image)))
    assert name == "scan.png" and size == len(image)
    with storage.local_copy(reference) as path:
        with fitz.open(path) as converted:
            assert converted.is_pdf and converted.page_count == 1
            assert converted[0].get_image_info()
