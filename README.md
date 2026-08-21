# PDF Intelligence App

Upload a batch of PDFs, provide one required JSON Schema, and receive contract-safe JSON with page-level evidence and a complete processing audit for every document.

## What is implemented

- Angular interface built around a results table: one row per PDF, one column per requested field
- Simple field builder (name + type) that generates the JSON Schema, with a JSON Schema editor behind a toggle for advanced use
- CSV download and combined JSON copy for the whole batch
- Per-file technical audit (read route, models, evidence, raw JSON) hidden behind a per-row Details expander
- FastAPI backend with streamed 200 MB upload enforcement
- Configurable batch limits (10 PDFs and 500 MB combined by default)
- Per-file batch rejection, so one bad PDF does not discard valid documents
- Bounded background queue to prevent unbounded memory growth under load
- Preflight 40-page hard limit before OCR or LLM work starts
- PDF signature, encryption, and corruption checks
- PyMuPDF text extraction for digital PDFs
- Conditional page fallback: PyMuPDF text → Mistral Small vision → Mistral OCR
- OCR policies: `auto` uses the full fallback chain, `always` forces OCR, `never` uses Python text only
- Chunked map/reduce extraction for long documents
- Required JSON Schema contracts with exact keys, nested shape, nullable missing values, and no extra fields
- Batch identity persisted per job, so reopening any file restores the whole batch view
- Concurrent batch processing with backoff-and-retry on Mistral rate limits
- Per-job audit metadata: Python/Vision/OCR page split, models, schema mode, duration, failure code and failure stage
- SQLite job persistence and background processing for local testing
- Prompt-injection boundary: PDF content is treated as untrusted data
- Local file deletion endpoint and PII-safe application logging

## Prerequisites

- Python 3.11+
- Node.js 22+
- One or more Mistral API keys for OCR and AI extraction

## First-time setup (Windows PowerShell)

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
Copy-Item .env.example .env
# Edit .env and set MISTRAL_API_KEYS=primary_key,fallback_key

cd ..\frontend
npm install
```

## Run locally

Terminal 1:

```powershell
cd backend
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000
```

Terminal 2:

```powershell
cd frontend
npm start
```

Open `http://localhost:4200`.

## Test

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest

cd ..\frontend
npm test -- --watch=false
npm run build
```

## Local vs production

The checked-in runtime uses local disk, SQLite, and a bounded in-process worker. It is appropriate for local testing and a single API instance. Do not run multiple API replicas against the same SQLite file or local upload directory.

The asynchronous API (job IDs plus polling) and separated storage/AI/job layers provide the migration boundary for horizontal scale. Before running multiple replicas, replace:

- local uploads with S3-compatible object storage;
- SQLite with PostgreSQL;
- the in-process ThreadPoolExecutor with SQS/Celery/Redis or another durable queue;
- local polling fan-out with a batch-status endpoint, SSE, or WebSockets when job volume warrants it;
- unrestricted API access with authentication, tenant isolation, rate limits, malware scanning, retention policies, and encrypted secrets.

Production capacity controls are configurable in backend/.env:

- MAX_BATCH_FILES=10
- MAX_BATCH_TOTAL_MB=500
- MAX_PENDING_JOBS=100
- LOCAL_WORKER_COUNT=10

LOCAL_WORKER_COUNT defaults to 10 so a full batch is processed concurrently rather than serially. Raise it only if the Mistral quota and machine memory allow, because OCR, PDF rendering, and model calls consume both. Queue saturation returns HTTP 429 instead of accepting unlimited work.

Because concurrent workers share one Mistral quota, rate-limited and transient upstream failures (429, 408, 5xx, timeouts, connection resets) are retried with exponential backoff and jitter across all configured keys, controlled by AI_MAX_RETRIES (default 3) and AI_RETRY_BASE_SECONDS (default 1.0). Client errors such as 400 and 401 fail immediately without retrying.

When multiple keys are configured, each Mistral OCR or structured-output operation tries the preferred key first and automatically retries once with the next key if it fails. Keys are never returned by the API or written to application logs.
