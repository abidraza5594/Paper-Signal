import fitz
import pytest
from pydantic import SecretStr

from app.config import Settings
from app.database import JobDatabase
from app.job_service import JobQueueFullError, JobRunner
from app.models import EvidenceItem, JobRecord, JobStatus, PartialExtraction
from app.extraction.types import ExtractionOutcome


def make_pdf(path):
    document = fitz.open()
    page = document.new_page()
    page.insert_text((72, 72), "Invoice INV-100 has a final total of INR 42 and is due tomorrow.")
    document.save(path)
    document.close()


def make_blank_pdf(path):
    document = fitz.open()
    document.new_page()
    document.save(path)
    document.close()


class FakeMistralService:
    def __init__(self, _settings):
        pass

    def ocr_pages(self, _path, _pages):
        return {}

    def extract_document(self, document, output_contract, progress=None, **kwargs):
        assert document.pages
        assert output_contract is not None
        if progress:
            progress(80, "Extracting")
        return ExtractionOutcome({"invoice_number": "INV-100", "total": "INR 42"}, [], [], [], True)


@pytest.mark.parametrize("provider", ["mistral", "gemini"])
def test_job_runner_completes_with_structured_result(tmp_path, monkeypatch, provider):
    from app import job_service

    monkeypatch.setattr(job_service, "GeminiDocumentService" if provider == "gemini" else "MistralDocumentService", FakeMistralService)
    pdf_path = tmp_path / "invoice.pdf"
    make_pdf(pdf_path)
    settings = Settings(
        data_dir=tmp_path / "data",
        ai_provider=provider,
        gemini_api_key=SecretStr("test"),
        mistral_api_key=SecretStr("test"),
        ocr_min_text_chars=10,
    )
    database = JobDatabase(settings.database_path)
    database.initialize()
    job = JobRecord(
        id="job-full",
        file_name="invoice.pdf",
        file_path=str(pdf_path),
        file_size=pdf_path.stat().st_size,
        instruction="Extract invoice number and total",
        output_template='{"type":"object"}',
    )
    database.create(job)
    runner = JobRunner(settings, database)

    runner._process(job.id)
    completed = database.get(job.id)
    runner.shutdown()

    assert completed is not None
    assert completed.status == JobStatus.completed
    assert completed.progress == 100
    assert completed.result["data"]["invoice_number"] == "INV-100"
    assert completed.result["document"]["page_count"] == 1
    assert completed.result["document"]["ai_provider"] == provider
    assert completed.result["document"]["verification_model"] == settings.verification_model


def run_blank_job(tmp_path, monkeypatch, fake_service):
    from app import job_service

    monkeypatch.setattr(job_service, "MistralDocumentService", fake_service)
    pdf_path = tmp_path / "scan.pdf"
    make_blank_pdf(pdf_path)
    settings = Settings(
        data_dir=tmp_path / "data",
        mistral_api_key=SecretStr("test"),
        ocr_min_text_chars=80,
        vision_min_text_chars=20,
    )
    database = JobDatabase(settings.database_path)
    database.initialize()
    job = JobRecord(
        id="job-scan",
        file_name="scan.pdf",
        file_path=str(pdf_path),
        file_size=pdf_path.stat().st_size,
        instruction="Extract visible text",
        output_template='{"type":"object"}',
        text_model=settings.mistral_text_model,
        vision_model=settings.mistral_text_model,
        ocr_model=settings.mistral_ocr_model,
    )
    database.create(job)
    runner = JobRunner(settings, database)
    runner._process(job.id)
    completed = database.get(job.id)
    runner.shutdown()
    return completed


def test_auto_mode_uses_vision_before_ocr(tmp_path, monkeypatch):
    class VisionSuccess:
        def __init__(self, _settings):
            pass

        def vision_page_text(self, image, page_number):
            assert image.startswith("data:image/jpeg;base64,")
            assert page_number == 1
            return "Vision recovered enough visible page text for structured extraction."

        def ocr_pages(self, _path, _pages):
            raise AssertionError("OCR must not run after successful vision transcription")

        def extract_document(self, document, _contract, **_kwargs):
            assert "Vision recovered" in document.pages[0].text
            return ExtractionOutcome({"source": "vision"}, [], [], [], True)

    completed = run_blank_job(tmp_path, monkeypatch, VisionSuccess)

    assert completed.status == JobStatus.completed
    assert completed.python_text_pages == 0
    assert completed.vision_attempted_pages == 1
    assert completed.vision_pages == 1
    assert completed.vision_failed_pages == 0
    assert completed.ocr_pages == 0


def test_auto_mode_falls_back_to_ocr_when_vision_is_unusable(tmp_path, monkeypatch):
    class VisionThenOcr:
        def __init__(self, _settings):
            pass

        def vision_page_text(self, _image, _page_number):
            return ""

        def ocr_pages(self, _path, pages):
            assert pages == [1]
            return {1: "OCR recovered the page after the vision result was unusable."}

        def extract_document(self, document, _contract, **_kwargs):
            assert "OCR recovered" in document.pages[0].text
            return ExtractionOutcome({"source": "ocr"}, [], [], [], True)

    completed = run_blank_job(tmp_path, monkeypatch, VisionThenOcr)

    assert completed.status == JobStatus.completed
    assert completed.vision_attempted_pages == 1
    assert completed.vision_pages == 0
    assert completed.vision_failed_pages == 1
    assert completed.ocr_pages == 1


def test_job_runner_rejects_work_when_bounded_queue_is_full(tmp_path, monkeypatch):
    settings = Settings(
        data_dir=tmp_path / "data",
        mistral_api_key=SecretStr("test"),
        max_pending_jobs=1,
    )
    database = JobDatabase(settings.database_path)
    database.initialize()
    runner = JobRunner(settings, database)
    monkeypatch.setattr(runner.executor, "submit", lambda *_args, **_kwargs: None)

    runner.submit("first")
    with pytest.raises(JobQueueFullError, match="queue is full"):
        runner.submit("second")
    runner.shutdown()


def test_unsatisfied_contract_is_failed_with_partial_data_and_audit(tmp_path, monkeypatch):
    class Unsatisfied:
        def __init__(self, _settings):
            pass

        def vision_page_text(self, _image, _page):
            return "Readable source evidence long enough for transcription."

        def extract_document(self, document, _contract, **_kwargs):
            return ExtractionOutcome({"known": "Readable"}, [{"fieldPath": "/known"}],
                                     [{"rejectionReason": "unresolved_conflict"}], [], False, ["/required"])
    result = run_blank_job(tmp_path, monkeypatch, Unsatisfied)
    assert result.status == JobStatus.failed
    assert result.failure_code == "SCHEMA_UNSATISFIED"
    assert result.result["data"] == {"known": "Readable"}
    assert result.result["document"]["schema_valid"] is False
    assert result.extraction_audit["decisions"][0]["rejectionReason"] == "unresolved_conflict"
