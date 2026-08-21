from __future__ import annotations

import logging
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, Response, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware

from .config import get_settings
from .database import JobDatabase
from .job_service import JobQueueFullError, JobRunner
from .models import (
    BatchFileRejection,
    BatchJobResponse,
    HealthResponse,
    JobPublic,
    JobRecord,
    JobStatus,
    OcrMode,
)
from .pdf_service import PdfProcessingError, PdfTextService
from .schema_service import OutputSchemaError, parse_json_schema_contract
from .storage import LocalStorage, UploadValidationError


logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
settings = get_settings()
settings.prepare_directories()
database = JobDatabase(settings.database_path)
storage = LocalStorage(settings.upload_dir, settings.max_upload_bytes)
runner = JobRunner(settings, database)


@asynccontextmanager
async def lifespan(_: FastAPI):
    database.initialize()
    yield
    runner.shutdown()


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type"],
)


@app.get("/api/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(
        ai_configured=settings.ai_configured,
        max_upload_mb=settings.max_upload_mb,
        max_pdf_pages=settings.max_pdf_pages,
        max_batch_files=settings.max_batch_files,
        max_batch_total_mb=settings.max_batch_total_mb,
        text_model=settings.mistral_text_model,
        vision_model=settings.mistral_text_model,
        ocr_model=settings.mistral_ocr_model,
    )


def _ensure_ai_configured() -> None:
    if not settings.ai_configured:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="MISTRAL_API_KEYS is not configured in backend/.env.",
        )


async def _prepare_job(
    file: UploadFile,
    output_template: str,
    ocr_mode: OcrMode,
    schema_mode: str,
    batch_id: str | None = None,
) -> JobRecord:
    path, size, original_name = await storage.save_pdf(file)
    try:
        page_count = PdfTextService.inspect_page_count(path)
        if page_count > settings.max_pdf_pages:
            raise PdfProcessingError(
                f"PDF rejected: {page_count} pages detected. Maximum allowed is "
                f"{settings.max_pdf_pages} pages."
            )
        return JobRecord(
            id=uuid.uuid4().hex,
            batch_id=batch_id,
            file_name=original_name,
            file_path=str(path),
            file_size=size,
            instruction="Extract only the fields defined by the supplied JSON Schema.",
            output_template=output_template.strip(),
            ocr_mode=ocr_mode,
            page_count=page_count,
            text_model=settings.mistral_text_model,
            vision_model=settings.mistral_text_model,
            ocr_model=settings.mistral_ocr_model,
            schema_mode=schema_mode,
        )
    except Exception:
        storage.delete(path)
        raise


def _enqueue_job(job: JobRecord) -> JobPublic:
    created = False
    try:
        database.create(job)
        created = True
        runner.submit(job.id)
    except Exception:
        if created:
            database.delete(job.id)
        storage.delete(job.file_path)
        raise
    return JobPublic.from_record(job)


@app.post("/api/jobs", response_model=JobPublic, status_code=status.HTTP_202_ACCEPTED)
async def create_job(
    file: UploadFile = File(...),
    output_template: str = Form(..., min_length=2, max_length=12000),
    ocr_mode: OcrMode = Form(default=OcrMode.auto),
) -> JobPublic:
    _ensure_ai_configured()
    try:
        contract = parse_json_schema_contract(output_template)
    except OutputSchemaError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc

    try:
        job = await _prepare_job(file, output_template, ocr_mode, contract.mode)
    except (UploadValidationError, PdfProcessingError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    try:
        return _enqueue_job(job)
    except JobQueueFullError as exc:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=str(exc)) from exc


@app.post(
    "/api/jobs/batch",
    response_model=BatchJobResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def create_job_batch(
    files: list[UploadFile] = File(...),
    output_template: str = Form(..., min_length=2, max_length=12000),
    ocr_mode: OcrMode = Form(default=OcrMode.auto),
) -> BatchJobResponse:
    _ensure_ai_configured()
    try:
        contract = parse_json_schema_contract(output_template)
    except OutputSchemaError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc

    if not files:
        raise HTTPException(status_code=422, detail="Select at least one PDF.")
    if len(files) > settings.max_batch_files:
        raise HTTPException(
            status_code=422,
            detail=f"A batch can contain at most {settings.max_batch_files} PDFs.",
        )
    declared_total = sum(file.size or 0 for file in files)
    if declared_total > settings.max_batch_total_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Batch exceeds the {settings.max_batch_total_mb} MB combined limit.",
        )

    batch_id = uuid.uuid4().hex
    prepared: list[JobRecord] = []
    rejected: list[BatchFileRejection] = []
    total_saved = 0
    for file in files:
        file_name = Path(file.filename or "document.pdf").name
        try:
            job = await _prepare_job(file, output_template, ocr_mode, contract.mode, batch_id)
            prepared.append(job)
            total_saved += job.file_size
        except (UploadValidationError, PdfProcessingError) as exc:
            rejected.append(BatchFileRejection(file_name=file_name, error=str(exc)))

    if total_saved > settings.max_batch_total_bytes:
        for job in prepared:
            storage.delete(job.file_path)
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Batch exceeds the {settings.max_batch_total_mb} MB combined limit.",
        )

    accepted: list[JobPublic] = []
    for index, job in enumerate(prepared):
        try:
            accepted.append(_enqueue_job(job))
        except JobQueueFullError as exc:
            rejected.append(BatchFileRejection(file_name=job.file_name, error=str(exc)))
        except Exception:
            for pending_job in prepared[index + 1 :]:
                storage.delete(pending_job.file_path)
            raise

    return BatchJobResponse(
        batch_id=batch_id,
        jobs=accepted,
        rejected=rejected,
        accepted_count=len(accepted),
        rejected_count=len(rejected),
    )


@app.get("/api/jobs/batch", response_model=list[JobPublic])
def get_job_batch(ids: str) -> list[JobPublic]:
    job_ids = [item.strip() for item in ids.split(",") if item.strip()]
    if not job_ids:
        raise HTTPException(status_code=422, detail="Provide at least one job ID.")
    if len(job_ids) > 50:
        raise HTTPException(status_code=422, detail="At most 50 job IDs can be checked at once.")
    return [JobPublic.from_record(job) for job in database.get_many(job_ids)]


@app.get("/api/batches/{batch_id}", response_model=list[JobPublic])
def get_batch(batch_id: str) -> list[JobPublic]:
    jobs = database.list_by_batch(batch_id)
    if not jobs:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Batch not found.")
    return [JobPublic.from_record(job) for job in jobs]


@app.get("/api/jobs", response_model=list[JobPublic])
def list_jobs(limit: int = 20) -> list[JobPublic]:
    safe_limit = min(max(limit, 1), 100)
    return [JobPublic.from_record(job) for job in database.list_recent(safe_limit)]


@app.get("/api/jobs/{job_id}", response_model=JobPublic)
def get_job(job_id: str) -> JobPublic:
    job = database.get(job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found.")
    return JobPublic.from_record(job)


@app.delete(
    "/api/jobs/{job_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
)
def delete_job(job_id: str) -> Response:
    job = database.get(job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found.")
    if job.status == JobStatus.processing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A processing job cannot be deleted. Wait for it to finish.",
        )
    storage.delete(job.file_path)
    database.delete(job_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
