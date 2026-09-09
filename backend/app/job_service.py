from __future__ import annotations

import logging
import time
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from pathlib import Path
from threading import BoundedSemaphore

from .config import Settings
from .database import JobDatabase
from .mistral_service import AiExtractionError, MistralDocumentService
from .models import ExtractionResult, JobStatus, OcrMode
from .pdf_service import PdfProcessingError, PdfTextService
from .schema_service import OutputSchemaError, parse_output_contract


logger = logging.getLogger(__name__)


class JobQueueFullError(RuntimeError):
    pass


class JobRunner:
    def __init__(self, settings: Settings, database: JobDatabase, storage=None):
        self.settings = settings
        self.database = database
        # The PDF may live in S3, so never assume file_path is a local path.
        self.storage = storage
        self.executor = ThreadPoolExecutor(
            max_workers=settings.local_worker_count,
            thread_name_prefix="pdf-worker",
        )
        self._capacity = BoundedSemaphore(settings.max_pending_jobs)
        self.pdf = PdfTextService(
            min_text_chars=settings.ocr_min_text_chars,
            chunk_chars=settings.text_chunk_chars,
        )

    def submit(self, job_id: str) -> None:
        if not self._capacity.acquire(blocking=False):
            raise JobQueueFullError(
                "Processing queue is full. Wait for active jobs to finish and try again."
            )
        try:
            self.executor.submit(self._run_queued, job_id)
        except Exception:
            self._capacity.release()
            raise

    def shutdown(self) -> None:
        self.executor.shutdown(wait=False, cancel_futures=False)

    def _run_queued(self, job_id: str) -> None:
        try:
            self._process(job_id)
        finally:
            self._capacity.release()

    @contextmanager
    def _pdf_file(self, reference: str):
        """The PDF may be in object storage, so fetch it once per job."""
        if self.storage is not None:
            with self.storage.local_copy(reference) as path:
                yield path
        else:
            yield Path(reference)

    def _process(self, job_id: str) -> None:
        job = self.database.get(job_id)
        if job is None:
            return
        with self._pdf_file(job.file_path) as pdf_path:
            self._extract(job_id, job, pdf_path)

    def _extract(self, job_id: str, job, pdf_path: Path) -> None:
        started = time.perf_counter()
        failure_stage = "Starting"
        try:
            failure_stage = "Reading PDF"
            self.database.update(
                job_id, status=JobStatus.processing, progress=5, stage="Reading PDF"
            )
            extracted = self.pdf.extract(pdf_path)
            self.database.update(
                job_id, progress=15, stage="Checking page text", page_count=extracted.page_count
            )

            ai = MistralDocumentService(self.settings)
            vision_attempted_pages = 0
            vision_pages = 0
            vision_failed_pages = 0

            if job.ocr_mode == OcrMode.always:
                python_text_pages = 0
                ocr_targets = [page.number for page in extracted.pages]
            elif job.ocr_mode == OcrMode.never:
                python_text_pages = extracted.page_count
                ocr_targets = []
            else:
                vision_targets = extracted.ocr_candidates
                python_text_pages = extracted.page_count - len(vision_targets)
                vision_attempted_pages = len(vision_targets)
                vision_text: dict[int, str] = {}
                ocr_targets: list[int] = []
                if vision_targets:
                    failure_stage = "Vision transcription"
                    for index, page_number in enumerate(vision_targets):
                        self.database.update(
                            job_id,
                            progress=16 + int(((index + 1) / len(vision_targets)) * 6),
                            stage=(
                                f"Trying vision on page {page_number} "
                                f"({index + 1} of {len(vision_targets)})"
                            ),
                            vision_attempted_pages=vision_attempted_pages,
                        )
                        try:
                            image = self.pdf.render_page_data_url(
                                pdf_path,
                                page_number,
                                dpi=self.settings.vision_render_dpi,
                            )
                            text = ai.vision_page_text(image, page_number).strip()
                            if len(text) >= self.settings.vision_min_text_chars:
                                vision_text[page_number] = text
                            else:
                                ocr_targets.append(page_number)
                        except Exception:
                            logger.warning(
                                "Vision fallback failed for job %s page %s; using OCR",
                                job_id,
                                page_number,
                            )
                            ocr_targets.append(page_number)
                    vision_pages = len(vision_text)
                    vision_failed_pages = len(ocr_targets)
                    if vision_text:
                        extracted = self.pdf.apply_page_text(extracted, vision_text)

            self.database.update(
                job_id,
                python_text_pages=python_text_pages,
                vision_attempted_pages=vision_attempted_pages,
                vision_pages=vision_pages,
                vision_failed_pages=vision_failed_pages,
            )

            if ocr_targets:
                failure_stage = "OCR"
                self.database.update(
                    job_id,
                    progress=24,
                    stage=f"Running OCR on {len(ocr_targets)} page(s)",
                    ocr_pages=len(ocr_targets),
                )
                ocr_text = ai.ocr_pages(pdf_path, ocr_targets)
                extracted = self.pdf.apply_ocr(extracted, ocr_text)

            failure_stage = "Structured extraction"
            self.database.update(
                job_id, progress=32, stage="Mapping schema fields to source evidence"
            )

            def on_progress(percent: int, stage: str) -> None:
                self.database.update(job_id, progress=percent, stage=stage)

            output_contract = parse_output_contract(job.output_template)
            if output_contract is None:
                raise OutputSchemaError("A JSON Schema is required for evidence-backed extraction.")
            outcome = ai.extract_document(
                extracted, output_contract,
                image_reader=lambda page: self.pdf.render_page_data_url(pdf_path, page, dpi=self.settings.vision_render_dpi),
                crop_reader=lambda page, box: self.pdf.render_page_data_url(pdf_path, page, dpi=self.settings.vision_render_dpi, bbox=box),
                progress=on_progress,
                debug=self.settings.extraction_debug,
            )
            duration_ms = round((time.perf_counter() - started) * 1000)
            result = ExtractionResult(
                request=job.instruction,
                data=outcome.data,
                evidence=[],
                warnings=outcome.warnings,
                document={
                    **extracted.metadata,
                    "file_name": job.file_name,
                    "file_size": job.file_size,
                    "ocr_pages": len(ocr_targets),
                    "python_text_pages": python_text_pages,
                    "vision_attempted_pages": vision_attempted_pages,
                    "vision_pages": vision_pages,
                    "vision_failed_pages": vision_failed_pages,
                    "text_sections": sum(len(p.layout.windows) for p in extracted.pages if p.layout),
                    "schema_valid": outcome.schema_valid,
                    "verification_model": self.settings.mistral_verification_model,
                    "validation_paths": outcome.validation_paths,
                    **({"extraction_debug": outcome.debug} if self.settings.extraction_debug else {}),
                    "text_model": self.settings.mistral_text_model,
                    "vision_model": (
                        self.settings.mistral_text_model if vision_attempted_pages else None
                    ),
                    "ocr_model": self.settings.mistral_ocr_model if ocr_targets else None,
                    "schema_mode": job.schema_mode,
                    "duration_ms": duration_ms,
                },
            )
            self.database.update(
                job_id,
                status=JobStatus.completed if outcome.schema_valid else JobStatus.failed,
                progress=100,
                stage="Completed" if outcome.schema_valid else "Schema cannot be satisfied from evidence",
                result=result.model_dump(mode="json"),
                extraction_audit={"provenance": outcome.provenance, "decisions": outcome.debug},
                error=None if outcome.schema_valid else "Source evidence cannot satisfy required schema constraints. Validated partial data is available in result.data.",
                duration_ms=duration_ms,
                failure_code=None if outcome.schema_valid else "SCHEMA_UNSATISFIED",
                failure_stage=None if outcome.schema_valid else "Final schema validation",
            )
        except Exception as exc:
            logger.error("PDF job %s failed (%s)", job_id, type(exc).__name__)
            duration_ms = round((time.perf_counter() - started) * 1000)
            if isinstance(exc, AiExtractionError):
                # The service classified it (rate limit, auth, provider outage, ...)
                # so the client can tell a retry from a real problem.
                failure_code = getattr(exc, "failure_code", "AI_EXTRACTION_ERROR")
            elif isinstance(exc, PdfProcessingError):
                failure_code = "PDF_PROCESSING_ERROR"
            elif isinstance(exc, OutputSchemaError):
                failure_code = "INVALID_OUTPUT_SCHEMA"
            else:
                failure_code = "PROCESSING_ERROR"
            self.database.update(
                job_id,
                status=JobStatus.failed,
                progress=100,
                stage="Failed",
                error=str(exc),
                duration_ms=duration_ms,
                failure_code=failure_code,
                failure_stage=failure_stage,
            )
