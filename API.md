# PaperSignal API Reference

Upload PDFs, send one JSON Schema, get contract-safe JSON back — one result per document,
with page-level evidence and a full processing audit.

Base URL (local): `http://localhost:8000`
Interactive docs: `GET /api/docs` · OpenAPI: `GET /api/openapi.json`

---

## 1. Two modes: open and key mode

| | Open mode (default) | Key mode |
|---|---|---|
| `REQUIRE_API_KEY` in `backend/.env` | `false` | `true` |
| Who can call `/api` | anyone who can reach the port | only holders of a valid key |
| Job ownership | jobs stored without an owner | every job belongs to the key that created it |
| Intended for | local development, the Angular console | giving the service to other people |

`GET /api/health` returns `require_api_key`, so a client can tell which mode it is talking to
before sending anything.

To switch to key mode:

```
REQUIRE_API_KEY=true
ADMIN_TOKEN=<a long random value>
```

Then restart the backend.

---

## 2. Authentication

Send the key on **every** `/api` request, in either header:

```
X-API-Key: ps_live_xxxxxxxxxxxxxxxxxxxxxxxxxxxx
```
```
Authorization: Bearer ps_live_xxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

`X-API-Key` wins if both are present.

Admin endpoints use a different, separate header — never an API key:

```
X-Admin-Token: <ADMIN_TOKEN from backend/.env>
```

### Key format and storage

A key looks like `ps_live_` followed by a URL-safe random string (24 bytes of entropy).

The raw key is shown **once**, at creation. The database stores only:

- a SHA-256 hash of the key, used to look it up on each request
- a short display prefix such as `ps_live_qTtT8j...`, so you can recognise a key in a list

There is no way to recover a lost key. Issue a new one and revoke the old one.

---

## 3. What an API key controls

Every key carries its own settings. They are independent per key.

| Control | What it does | What happens when exceeded |
|---|---|---|
| **Ownership / isolation** | The key that created a job is the only one that can read, poll, list, or delete it. | Another key asking for that job id gets **404**, not 403 — the service does not reveal that the job exists. |
| **Rate limit** | Requests per minute, sliding 60-second window, counted per key. Default `DEFAULT_RATE_LIMIT_PER_MINUTE` (60). | **429** with a `Retry-After` header in seconds. |
| **Monthly quota** | Accepted documents per calendar month (UTC). Default `DEFAULT_MONTHLY_DOCUMENT_QUOTA` (1000). Checked *before* work starts. | **402 Payment Required**, and nothing is processed. |
| **Revocation** | An admin can disable a key at any time. | **401** on the next call, immediately. |

Notes that matter in practice:

- **Rejected files are not billed.** If you send 5 PDFs and 2 are corrupt, only the 3 accepted
  documents count against the quota.
- **Usage is counted at submit time**, not at completion. A job that later fails still counts.
- **Pages are recorded too** (alongside documents), for future per-page billing. Quota
  enforcement currently uses documents only.
- **Rate limiting is in-process.** With several API replicas behind a load balancer, each
  replica enforces its own share of the limit. Move it to Redis before scaling out.

---

## 4. Endpoints

### 4.1 Public

#### `GET /api/health`
No auth. Use it to check the service is up and to discover its limits.

```json
{
  "status": "ok",
  "ai_configured": true,
  "require_api_key": true,
  "max_upload_mb": 200,
  "max_pdf_pages": 40,
  "max_batch_files": 10,
  "max_batch_total_mb": 500,
  "text_model": "mistral-small-2603",
  "vision_model": "mistral-small-2603",
  "ocr_model": "mistral-ocr-4-0"
}
```

---

### 4.2 Submitting work

#### `POST /api/jobs/batch` — submit one or more PDFs *(recommended)*

`multipart/form-data`:

| Field | Type | Required | Notes |
|---|---|---|---|
| `files` | file (repeatable) | yes | One or more PDFs. Repeat the field per file. |
| `output_template` | string | yes | A JSON Schema. 2–12000 characters. |
| `ocr_mode` | `auto` \| `always` \| `never` | no | Defaults to `auto`. |

```bash
curl -X POST http://localhost:8000/api/jobs/batch \
  -H "X-API-Key: ps_live_..." \
  -F "files=@invoice-a.pdf" \
  -F "files=@invoice-b.pdf" \
  -F 'output_template={"type":"object","properties":{"total":{"type":"number"}}}' \
  -F "ocr_mode=auto"
```

**202 Accepted** — work is queued, not finished. Poll for results.

```json
{
  "batch_id": "48b5ece785b64177b968de64720841ec",
  "accepted_count": 2,
  "rejected_count": 1,
  "jobs": [ { "id": "...", "status": "queued", "progress": 0, "...": "..." } ],
  "rejected": [ { "file_name": "broken.pdf", "error": "The uploaded file is not a valid PDF." } ]
}
```

A bad file never discards the good ones: it lands in `rejected` while the rest are accepted.

#### `POST /api/jobs` — submit a single PDF
Same fields but `file` (singular) instead of `files`. Returns a single job object. Prefer the
batch endpoint even for one file — it gives you a `batch_id` and the same polling shape.

---

### 4.3 Reading results

#### `GET /api/batches/{batch_id}`
Every job in the batch, in submission order. This is the normal way to poll.

#### `GET /api/jobs/{job_id}`
One job.

#### `GET /api/jobs/batch?ids=id1,id2,id3`
Several specific jobs in one call. Maximum 50 ids.

#### `GET /api/jobs?limit=20`
Recent jobs belonging to your key. `limit` is clamped to 1–100.

All of these return `JobPublic` objects:

| Field | Meaning |
|---|---|
| `id`, `batch_id` | Job id, and the batch it was submitted with. |
| `file_name`, `file_size` | As uploaded. |
| `status` | `queued` → `processing` → `completed` or `failed`. |
| `progress`, `stage` | 0–100 and a human-readable stage such as `Reading PDF`. |
| `result` | `null` until complete. Then `{ "data": {...}, "evidence": [...], "warnings": [...] }`. |
| `error`, `failure_code`, `failure_stage` | Set only when `status` is `failed`. |
| `page_count` | Pages in the PDF. |
| `python_text_pages` | Pages read from the embedded text layer (no AI cost). |
| `vision_attempted_pages`, `vision_pages`, `vision_failed_pages` | Pages sent to the vision model, read successfully, and failed. |
| `ocr_pages` | Pages that needed the OCR fallback. |
| `text_model`, `vision_model`, `ocr_model` | Models actually used. |
| `ocr_mode`, `schema_mode` | The policy and contract mode for this job. |
| `output_template` | The JSON Schema you sent. |
| `duration_ms` | Total processing time. |
| `created_at`, `updated_at` | ISO-8601 UTC. |

`result.data` matches your schema exactly: same keys, same nesting, missing values as `null`,
and anything outside the schema removed. `result.evidence` is a list of
`{ label, page, evidence }` showing where each value came from.

#### `DELETE /api/jobs/{job_id}`
Deletes the job and its stored PDF. **204** on success, **409** while the job is still
processing, **404** if it is not yours.

---

### 4.4 Usage

#### `GET /api/usage`
What your key has spent this month. Requires a key even in open mode.

```json
{
  "api_key": {
    "id": "692076be85704503230fd7746ba4c870",
    "name": "Partner Co",
    "key_prefix": "ps_live_qTtT8j...",
    "rate_limit_per_minute": 120,
    "monthly_document_quota": 5000,
    "documents_this_month": 143,
    "created_at": "2026-08-21T07:45:00+00:00",
    "last_used_at": "2026-08-21T11:02:11+00:00",
    "revoked_at": null
  },
  "period": "2026-08",
  "documents_this_month": 143,
  "monthly_document_quota": 5000,
  "documents_remaining": 4857,
  "rate_limit_per_minute": 120
}
```

---

### 4.5 Admin — issuing and revoking keys

All three require `X-Admin-Token` and return **503** if `ADMIN_TOKEN` is not configured.

#### `POST /api/admin/keys`

```bash
curl -X POST http://localhost:8000/api/admin/keys \
  -H "X-Admin-Token: $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name":"Acme Corp","rate_limit_per_minute":120,"monthly_document_quota":5000}'
```

`rate_limit_per_minute` and `monthly_document_quota` are optional and fall back to the
`DEFAULT_*` values in `.env`.

**201 Created** — `key` appears here and nowhere else, ever:

```json
{
  "key": "ps_live_qTtT8jvk0ooM...",
  "api_key": { "id": "6920...", "name": "Acme Corp", "key_prefix": "ps_live_qTtT8j...", "...": "..." }
}
```

#### `GET /api/admin/keys`
All keys with their current month's usage. Never returns raw key values.

#### `DELETE /api/admin/keys/{key_id}`
**204** on success, **409** if already revoked, **404** if unknown. Takes effect immediately.

### CLI alternative

Works on the server without `ADMIN_TOKEN` or HTTP:

```powershell
cd backend
.\.venv\Scripts\python.exe manage_keys.py create "Acme Corp" --rate-limit 120 --quota 5000
.\.venv\Scripts\python.exe manage_keys.py list
.\.venv\Scripts\python.exe manage_keys.py revoke <key_id>
```

---

## 5. Status codes

| Code | When | What to do |
|---|---|---|
| **200** | Read succeeded. | — |
| **201** | Key created. | Store the `key` value now. |
| **202** | Work accepted and queued. | Poll `/api/batches/{batch_id}`. |
| **204** | Deleted or revoked. | — |
| **400** | Bad PDF: not a PDF, encrypted, corrupt, empty, or over the page limit. | Fix or split the file. |
| **401** | Missing, unknown, or revoked key; or a bad admin token. | Check the key. If revoked, request a new one. |
| **402** | Monthly document quota would be exceeded. | Wait for the next period or ask for a higher quota. |
| **404** | Job or batch not found — including when it belongs to another key. | Check the id. |
| **409** | Deleting a job that is still processing, or revoking an already-revoked key. | Wait for the job to finish. |
| **413** | Batch is over the combined size limit. | Send fewer or smaller files. |
| **422** | Invalid JSON Schema, no files, or too many files in one batch. | See `detail` for the exact reason. |
| **429** | Per-key rate limit, **or** the server's processing queue is full. | Honour `Retry-After` and back off. |
| **503** | AI keys not configured on the server, or `ADMIN_TOKEN` missing for admin routes. | Server-side configuration. |

When a job itself fails, the HTTP call still succeeds — check `status: "failed"` and read
`failure_code`:

| `failure_code` | Meaning |
|---|---|
| `PDF_PROCESSING_ERROR` | The PDF could not be read: corrupt, encrypted, or over the page limit. |
| `AI_EXTRACTION_ERROR` | Every configured AI key failed for this document, after retries. |
| `PROCESSING_ERROR` | Anything else; check `failure_stage` and the server log with the job id. |

---

## 6. Limits

Set in `backend/.env`; the current values are always visible on `GET /api/health`.

| Limit | Default | Setting |
|---|---|---|
| Files per batch | 10 | `MAX_BATCH_FILES` |
| Combined batch size | 500 MB | `MAX_BATCH_TOTAL_MB` |
| Single file size | 200 MB | `MAX_UPLOAD_MB` |
| Pages per PDF | 40 | `MAX_PDF_PAGES` |
| Documents processed in parallel | 10 | `LOCAL_WORKER_COUNT` |
| Jobs waiting in the queue | 100 | `MAX_PENDING_JOBS` |
| Default rate limit for a new key | 60 / minute | `DEFAULT_RATE_LIMIT_PER_MINUTE` |
| Default monthly quota for a new key | 1000 documents | `DEFAULT_MONTHLY_DOCUMENT_QUOTA` |

The page limit is enforced *before* any AI or OCR work starts, so an oversized PDF costs nothing.

---

## 7. The JSON Schema you send

`output_template` must be a real JSON Schema — an example object is rejected.

Required: root `"type": "object"` and a non-empty `"properties"`.

```json
{
  "type": "object",
  "properties": {
    "trainName":   { "type": "string" },
    "trainNumber": { "type": "number" },
    "startFrom":   { "type": "string" },
    "stops":       { "type": "array", "items": { "type": "string" } },
    "fare": {
      "type": "object",
      "properties": {
        "amount":   { "type": "number" },
        "currency": { "type": "string" }
      }
    }
  }
}
```

Rules:

- Supported types: `string`, `number`, `integer`, `boolean`, `array`, `object`, `null`.
- Nesting up to 8 levels; at most 100 properties per object; every object needs at least one property.
- `$ref`, `allOf`, `anyOf`, `oneOf`, and `not` are **not** supported.
- Keys must be quoted. `{trainName:"string"}` is not valid JSON, and `{"trainName":"string"}`
  is an example object, not a schema — both are rejected.
- Anything the PDF does not contain comes back as `null`. Anything outside the schema is dropped.

### `ocr_mode`

| Value | Behaviour |
|---|---|
| `auto` *(default)* | Embedded text first, vision only for unreadable pages, OCR only where vision fails. Cheapest and usually best. |
| `always` | Force OCR on every page. Use for scans where the embedded text layer is wrong. |
| `never` | Embedded text only. No AI page reading, no OCR. Fails on image-only PDFs. |

---

## 8. End-to-end example

```bash
KEY="ps_live_..."
BASE="http://localhost:8000"

# 1. submit
BATCH=$(curl -s -X POST "$BASE/api/jobs/batch" \
  -H "X-API-Key: $KEY" \
  -F "files=@a.pdf" -F "files=@b.pdf" \
  -F 'output_template={"type":"object","properties":{"total":{"type":"number"}}}' \
  | python -c "import sys,json; print(json.load(sys.stdin)['batch_id'])")

# 2. poll until nothing is queued or processing
while true; do
  DONE=$(curl -s -H "X-API-Key: $KEY" "$BASE/api/batches/$BATCH" \
    | python -c "import sys,json; j=json.load(sys.stdin); print(all(x['status'] in ('completed','failed') for x in j))")
  [ "$DONE" = "True" ] && break
  sleep 2
done

# 3. read the results
curl -s -H "X-API-Key: $KEY" "$BASE/api/batches/$BATCH" \
  | python -c "
import sys, json
for job in json.load(sys.stdin):
    print(job['file_name'], '->', (job.get('result') or {}).get('data'))
"
```

Poll every 1–3 seconds. There is no webhook or streaming endpoint yet.

---

## 9. Things to know before you rely on this

- **One API instance only.** Jobs, keys, and usage live in SQLite, and uploads live on local
  disk. Running two replicas against the same files will cause lock errors. PostgreSQL and
  object storage are the next step.
- **Rate limiting is per replica**, as noted above.
- **Uploaded PDFs stay on the server** until deleted via `DELETE /api/jobs/{job_id}`. There is
  no automatic retention policy.
- **No TLS in the stack.** Put it behind a reverse proxy with HTTPS before exposing it —
  API keys travel in a header and must not cross plain HTTP.
- **No malware scanning** of uploads.
- Page content is sent to Mistral only when a page needs AI reading or OCR. API keys are never
  logged or returned by any endpoint.
