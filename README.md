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
- Preflight page limit (50 by default) enforced before OCR or LLM work starts
- PDF signature, encryption, and corruption checks
- PyMuPDF text extraction for digital PDFs
- Conditional page fallback: PyMuPDF text → Mistral Small vision → Mistral OCR
- OCR policies: `auto` uses the full fallback chain, `always` forces OCR, `never` uses Python text only
- Evidence-first extraction with preserved table geometry, local candidates, independent verification, and deterministic final assembly
- JSON Schema contracts preserved as supplied, including nullability, required fields, local references, composition, formats, and additional properties
- Per-field internal provenance and optional debug decisions; unsupported facts are withheld
- PDF and PNG/JPEG/TIFF/WebP inputs (images enter the same pipeline as canonical PDF pages)
- Batch identity persisted per job, so reopening any file restores the whole batch view
- API-key service mode: hashed keys, per-client job isolation, per-key rate limits, monthly document quotas, usage reporting, and admin endpoints plus a `manage_keys.py` CLI
- Concurrent batch processing with backoff-and-retry on Mistral rate limits
- Per-job audit metadata: Python/Vision/OCR page split, models, schema mode, duration, failure code and failure stage
- SQLite persistence for jobs, API keys, and monthly usage
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

The extraction architecture, supported normalization rules, debugging controls, and known limitations are documented in [docs/EXTRACTION_PIPELINE.md](docs/EXTRACTION_PIPELINE.md).
Actual model comparisons, supplied-document results, and remaining accuracy gaps are recorded in [docs/EXTRACTION_VALIDATION.md](docs/EXTRACTION_VALIDATION.md).
Gemini configuration and its separately measured migration checks are documented in [docs/GEMINI_PROVIDER.md](docs/GEMINI_PROVIDER.md).

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest

cd ..\frontend
npm test -- --watch=false
npm run build
```

## Using it as an API service

The developer documentation website is served by the frontend at `/documentation`. It has 22 navigable pages in simple English, a quick start, all 12 API operations, a dated test-results page, searchable topics, copyable examples and downloadable Python/Node.js clients. The `/api/docs` Swagger explorer remains available separately.

Documentation authoring and deployment instructions: [docs/WEBSITE.md](docs/WEBSITE.md).

The service ships in open mode so the local console works without a key. To let other
people call it, turn on key mode in `backend/.env`:

```
REQUIRE_API_KEY=true
ADMIN_TOKEN=<a long random value>
```

With key mode on, every `/api` call needs a key. `GET /api/health` reports
`require_api_key` so a client can tell which mode the service is in.

### Issuing keys

From the machine running the service:

```powershell
cd backend
.\.venv\Scripts\python.exe manage_keys.py create "Acme Corp" --rate-limit 120 --quota 5000
.\.venv\Scripts\python.exe manage_keys.py list
.\.venv\Scripts\python.exe manage_keys.py revoke <key_id>
```

Or over HTTP, using `ADMIN_TOKEN`:

```bash
curl -X POST http://localhost:8000/api/admin/keys   -H "X-Admin-Token: $ADMIN_TOKEN" -H "Content-Type: application/json"   -d '{"name":"Acme Corp","rate_limit_per_minute":120,"monthly_document_quota":5000}'
```

The raw key is returned once and never stored in clear text: only a SHA-256 hash and a
short display prefix are kept, so a stolen database cannot be used to call the API.

### Calling the API

Send the key as `X-API-Key`, or as `Authorization: Bearer <key>`.

```bash
# 1. submit a batch, one JSON Schema for every file
curl -X POST http://localhost:8000/api/jobs/batch   -H "X-API-Key: ps_live_..."   -F "files=@invoice-a.pdf" -F "files=@invoice-b.pdf"   -F 'output_template={"type":"object","properties":{"total":{"type":"number"}}}'   -F "ocr_mode=auto"
# -> 202 {"batch_id":"...","jobs":[{"id":"...","status":"queued",...}],"rejected":[],...}

# 2. poll the whole batch
curl -H "X-API-Key: ps_live_..." http://localhost:8000/api/batches/<batch_id>

# 3. or poll one job
curl -H "X-API-Key: ps_live_..." http://localhost:8000/api/jobs/<job_id>

# 4. check what the key has spent this month
curl -H "X-API-Key: ps_live_..." http://localhost:8000/api/usage
```

Interactive docs live at `/api/docs`. The full endpoint reference — every route, every field,
every status code, and exactly what an API key controls — is in [API.md](API.md).

### What a key controls

| Behaviour | Detail |
|---|---|
| Isolation | A key only ever sees, polls, and deletes its own jobs. Another client's job id returns 404. |
| Rate limit | Per key, per minute. Exceeding it returns 429 with a `Retry-After` header. |
| Monthly quota | Counted in accepted documents per calendar month. Exceeding it returns 402. Rejected files are not billed. |
| Revocation | Revoked keys return 401 immediately. |

Rate limiting is in-process, so each API replica enforces its own share; move it to Redis
before running several replicas behind a load balancer.

## Deploying

[RUNBOOK.md](RUNBOOK.md) (Hinglish) documents the live AWS deployment: which services were
created and why, every command that ran, the monthly cost, how to delete uploaded PDFs, how
clients integrate with an API key, and the full teardown checklist.

[DEPLOYMENT.md](DEPLOYMENT.md) walks through a single AWS free-tier EC2 instance with
automatic HTTPS: what the free tier covers, the 1 GB RAM constraints, the setup script in
`infra/`, and how to tear it down without leaving billable resources behind.

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
