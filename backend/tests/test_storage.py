from io import BytesIO

import pytest
from starlette.datastructures import UploadFile

from app.storage import LocalStorage, UploadValidationError


@pytest.mark.asyncio
async def test_streamed_pdf_upload_is_saved(tmp_path):
    storage = LocalStorage(tmp_path, max_upload_bytes=1024)
    upload = UploadFile(filename="sample.pdf", file=BytesIO(b"%PDF-1.4\nhello"))

    path, size, name = await storage.save_pdf(upload)

    assert path.exists()
    assert size == 14
    assert name == "sample.pdf"


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

