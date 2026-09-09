from __future__ import annotations

import logging
import secrets
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, Response, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.responses import FileResponse

from .api_keys import (
    ApiKeyError,
    ApiKeyRecord,
    ApiKeyStore,
    RateLimitExceeded,
    RateLimiter,
    current_period,
)
from .config import get_settings
from .database import JobDatabase
from .job_service import JobQueueFullError, JobRunner
from .models import (
    ApiKeyCreated,
    ApiKeyCreateRequest,
    ApiKeyPublic,
    BatchFileRejection,
    BatchJobResponse,
    HealthResponse,
    JobPublic,
    JobRecord,
    JobStatus,
    OcrMode,
    UsageResponse,
)
from .pdf_service import PdfProcessingError, PdfTextService
from .schema_service import OutputSchemaError, parse_json_schema_contract
from .storage import UploadValidationError, build_storage


logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
settings = get_settings()
settings.prepare_directories()
def _build_database():
    """DynamoDB when a table is configured, SQLite otherwise."""
    if settings.jobs_table:
        from .dynamo import DynamoJobDatabase
        return DynamoJobDatabase(settings.jobs_table)
    return JobDatabase(settings.database_path)


def _build_api_keys():
    if settings.api_keys_table:
        from .dynamo import DynamoApiKeyStore
        return DynamoApiKeyStore(settings.api_keys_table, settings.usage_table)
    return ApiKeyStore(settings.api_keys_database_path)


database = _build_database()
storage = build_storage(settings)
runner = JobRunner(settings, database, storage)
api_keys = _build_api_keys()
rate_limiter = RateLimiter()


@asynccontextmanager
async def lifespan(_: FastAPI):
    database.initialize()
    api_keys.initialize()
    if settings.require_api_key and not settings.admin_token_value:
        logging.getLogger(__name__).warning(
            "REQUIRE_API_KEY is on but ADMIN_TOKEN is not set: no new keys can be issued."
        )
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
    allow_headers=["Content-Type", "X-API-Key", "Authorization"],
)


def _extract_key(x_api_key: str | None, authorization: str | None) -> str | None:
    if x_api_key and x_api_key.strip():
        return x_api_key.strip()
    if authorization and authorization.lower().startswith("bearer "):
        candidate = authorization[7:].strip()
        return candidate or None
    return None


def require_caller(
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
    authorization: str | None = Header(default=None),
) -> ApiKeyRecord | None:
    """Resolve the calling client.

    With REQUIRE_API_KEY off (local development) an anonymous caller is allowed and
    its jobs are stored without an owner. With it on, a valid key is mandatory and
    every job is scoped to that key.
    """
    raw_key = _extract_key(x_api_key, authorization)
    if raw_key is None:
        if settings.require_api_key:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Send your key in the X-API-Key header.",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return None

    record = api_keys.find_by_raw_key(raw_key)
    if record is None or not record.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="This API key is not valid or has been revoked.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        rate_limiter.check(record.id, record.rate_limit_per_minute)
    except RateLimitExceeded as exc:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Rate limit of {record.rate_limit_per_minute} requests per minute exceeded.",
            headers={"Retry-After": str(exc.retry_after_seconds)},
        ) from exc
    api_keys.touch(record.id)
    return record


def require_admin(
    x_admin_token: str | None = Header(default=None, alias="X-Admin-Token"),
) -> None:
    expected = settings.admin_token_value
    if not expected:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="ADMIN_TOKEN is not configured, so keys cannot be managed over HTTP.",
        )
    if not x_admin_token or not secrets.compare_digest(x_admin_token, expected):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="A valid X-Admin-Token header is required.",
        )


def _owner_id(caller: ApiKeyRecord | None) -> str | None:
    return caller.id if caller else None


def _check_quota(caller: ApiKeyRecord | None, documents: int) -> None:
    if caller is None or documents <= 0:
        return
    used = api_keys.documents_used(caller.id)
    if used + documents > caller.monthly_document_quota:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail=(
                f"Monthly quota of {caller.monthly_document_quota} documents would be exceeded "
                f"({used} already used this period)."
            ),
        )


@app.get(
    "/api/health",
    response_model=HealthResponse,
    summary="Service health and limits",
    description="Public. No API key needed. Use it to check the service is up and read its limits.",
)
def health() -> HealthResponse:
    return HealthResponse(
        ai_configured=settings.ai_configured,
        require_api_key=settings.require_api_key,
        max_upload_mb=settings.max_upload_mb,
        max_pdf_pages=settings.max_pdf_pages,
        max_batch_files=settings.max_batch_files,
        max_batch_total_mb=settings.max_batch_total_mb,
        text_model=settings.text_model,
        vision_model=settings.text_model,
        ocr_model=settings.ocr_model,
    )


def _ensure_ai_configured() -> None:
    if not settings.ai_configured:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="The selected AI provider's API key is not configured on the server.",
        )


async def _prepare_job(
    file: UploadFile,
    output_template: str,
    ocr_mode: OcrMode,
    schema_mode: str,
    batch_id: str | None = None,
    api_key_id: str | None = None,
) -> JobRecord:
    path, size, original_name = await storage.save_pdf(file)
    try:
        # `path` is an opaque reference: an S3 key in the cloud, a filename locally.
        # Ask the storage for readable bytes instead of assuming a local file.
        with storage.local_copy(path) as readable:
            page_count = PdfTextService.inspect_page_count(readable)
        if page_count > settings.max_pdf_pages:
            raise PdfProcessingError(
                f"PDF rejected: {page_count} pages detected. Maximum allowed is "
                f"{settings.max_pdf_pages} pages."
            )
        return JobRecord(
            id=uuid.uuid4().hex,
            batch_id=batch_id,
            api_key_id=api_key_id,
            file_name=original_name,
            file_path=path,
            file_size=size,
            instruction="Extract only the fields defined by the supplied JSON Schema.",
            output_template=output_template.strip(),
            ocr_mode=ocr_mode,
            page_count=page_count,
            text_model=settings.text_model,
            vision_model=settings.text_model,
            ocr_model=settings.ocr_model,
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


@app.post(
    "/api/v1/extractions",
    response_model=BatchJobResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Submit documents for extraction",
    description=(
        "Upload one or more PDFs together with a JSON Schema describing the fields you "
        "want. Returns immediately with an extraction id; poll it for the results."
    ),
)
async def submit_extraction(
    files: list[UploadFile] = File(...),
    output_template: str = Form(..., min_length=2, max_length=12000),
    ocr_mode: OcrMode = Form(default=OcrMode.auto),
    caller: ApiKeyRecord | None = Depends(require_caller),
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
    _check_quota(caller, len(files))
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
            job = await _prepare_job(
                file, output_template, ocr_mode, contract.mode, batch_id, _owner_id(caller)
            )
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

    if caller and accepted:
        api_keys.record_documents(
            caller.id, len(accepted), sum(job.page_count or 0 for job in prepared)
        )

    return BatchJobResponse(
        batch_id=batch_id,
        jobs=accepted,
        rejected=rejected,
        accepted_count=len(accepted),
        rejected_count=len(rejected),
    )


@app.get(
    "/api/v1/extractions/{extraction_id}",
    response_model=list[JobPublic],
    summary="Get extraction status and results",
    description=(
        "Returns one entry per submitted document. Poll until every entry reports "
        "`completed` or `failed`; the extracted JSON is in `result.data`."
    ),
)
def get_extraction(
    extraction_id: str, caller: ApiKeyRecord | None = Depends(require_caller)
) -> list[JobPublic]:
    jobs = database.list_by_batch(extraction_id, _owner_id(caller))
    if not jobs:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Extraction not found.")
    return [JobPublic.from_record(job) for job in jobs]


@app.get(
    "/api/v1/account",
    response_model=UsageResponse,
    summary="Your API key's limits and usage",
    description="Shows the calling key's rate limit, monthly quota, and what is left.",
)
def get_account(caller: ApiKeyRecord | None = Depends(require_caller)) -> UsageResponse:
    """What the calling key has spent this month and what is left."""
    if caller is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Send your key in the X-API-Key header to see its usage.",
        )
    used = api_keys.documents_used(caller.id)
    return UsageResponse(
        api_key=caller.to_public(used),
        period=current_period(),
        documents_this_month=used,
        monthly_document_quota=caller.monthly_document_quota,
        documents_remaining=max(0, caller.monthly_document_quota - used),
        rate_limit_per_minute=caller.rate_limit_per_minute,
    )


@app.post(
    "/api/v1/keys",
    response_model=ApiKeyCreated,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_admin)],
    summary="Create an API key",
    description=(
        "Issues a key for one client. Needs the X-Admin-Token header. The raw key is "
        "returned once and cannot be recovered later. List and revoke keys on the "
        "server with manage_keys.py."
    ),
)
def create_api_key(payload: ApiKeyCreateRequest) -> ApiKeyCreated:
    """Issue a key. The raw value is returned once and never stored in clear text."""
    try:
        record, raw_key = api_keys.create(
            name=payload.name,
            rate_limit_per_minute=payload.rate_limit_per_minute
            or settings.default_rate_limit_per_minute,
            monthly_document_quota=payload.monthly_document_quota
            or settings.default_monthly_document_quota,
        )
    except ApiKeyError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return ApiKeyCreated(key=raw_key, api_key=record.to_public())


@app.delete(
    "/api/v1/extractions/{extraction_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    summary="Delete an extraction and its uploaded files",
    description=(
        "Removes every document in the extraction, its stored PDF, and its results. "
        "Returns 409 while any document is still processing."
    ),
)
def delete_extraction(
    extraction_id: str, caller: ApiKeyRecord | None = Depends(require_caller)
) -> Response:
    jobs = database.list_by_batch(extraction_id, _owner_id(caller))
    if not jobs:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Extraction not found.")
    if any(job.status == JobStatus.processing for job in jobs):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This extraction is still processing. Wait for it to finish.",
        )
    for job in jobs:
        storage.delete(job.file_path)
        database.delete(job.id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@app.api_route(
    "/api/{rest:path}",
    methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    include_in_schema=False,
)
def unknown_api_route(rest: str):
    """Any /api path that no route above matched.

    Declared after every real route so it only catches leftovers. Without it the
    static mount below would answer, giving 405 or an HTML page for a wrong URL.
    """
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"Unknown API endpoint: /api/{rest}. See /api/docs for the current endpoints.",
    )


# --- the web console, served by the same container -------------------------
#
# One origin for the site and the API means no CORS between them, and no second
# service to deploy. Mounted last so every /api route is matched first.

class SpaFiles(StaticFiles):
    """Static files, but unknown paths fall back to index.html.

    The console is a single-page app: /documentation is a client-side route with
    no file behind it, so a plain static server would 404 on a page refresh.
    """

    async def get_response(self, path: str, scope):
        try:
            return await super().get_response(path, scope)
        except StarletteHTTPException as exc:
            # An unknown /api path is a client error, not a page. Returning HTML
            # there would hide a wrong URL behind a 200.
            if exc.status_code == 404 and not scope["path"].startswith("/api"):
                return FileResponse(Path(self.directory) / "index.html")
            raise


_web_root = Path(__file__).resolve().parent.parent / "web"
if _web_root.is_dir():
    app.mount("/", SpaFiles(directory=str(_web_root), html=True), name="web")
