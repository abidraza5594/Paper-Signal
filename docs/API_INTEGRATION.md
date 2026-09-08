# PaperSignal API integration guide

Reviewed 8 September 2026. API version: `0.1.0`. Audience: developers integrating PDF extraction into another application. This is the current integration reference; it supersedes older examples in the deployment runbook.

**Latest test finding:** uploads and job-management APIs worked, but real extraction failed locally and on AWS. Read [the dated results](API_TEST_RESULTS.md) before treating the service as operational. The documentation website uses the simpler page copy in website_plain_english.py.

## 1. Can another application use this service

**Yes.** Your application's backend can call PaperSignal over HTTPS without installing its Angular frontend. Upload PDFs and a JSON Schema, save the returned extraction ID, poll it, and consume `result.data`. Each application can have a dedicated API key with its own document ownership, request limit and document quota.

Recommended flow:

```text
Your frontend -> Your backend and user authorization
             -> PaperSignal HTTPS API and client key
             -> PDF reading and Mistral extraction
             <- Job status and structured JSON
Your frontend <- Validated result saved in your application
```

The current architecture supports a controlled single-instance integration. Durable restart recovery, strict concurrent quota enforcement and high availability need additional work. See [SERVICE_ASSESSMENT.md](SERVICE_ASSESSMENT.md) for the manager assessment.

## 2. Connection and verified deployment

| Resource | Address |
|---|---|
| AWS base URL | `https://papersignal.duckdns.org` |
| Local base URL | `http://localhost:8000` |
| Interactive documentation | [Swagger UI](https://papersignal.duckdns.org/api/docs) |
| Machine-readable contract | [OpenAPI JSON](https://papersignal.duckdns.org/api/openapi.json) |

Paths below already contain `/api`; do not add it twice. There is no versioned URL prefix. You can import OpenAPI into Postman. Authentication is currently represented as ordinary header parameters, not an OpenAPI security scheme; set the request headers explicitly in Swagger/generated clients.

Live checks returned 200 for health, Swagger and OpenAPI, and 401 for usage without a key. The deployed OpenAPI lists the same 12 business operations as local source. Authenticated extraction was subsequently tested and failed at the structured extraction stage. `ai_configured: true` means credentials exist in configuration, not that extraction succeeds.

## 3. Authentication and ownership

Consumer requests use either header:

```http
X-API-Key: <YOUR_CLIENT_API_KEY>
```

```http
Authorization: Bearer <YOUR_CLIENT_API_KEY>
```

A nonempty `X-API-Key` takes precedence if both are supplied. Missing, invalid or revoked keys return 401 in service mode (`REQUIRE_API_KEY=true`). Health, Swagger and OpenAPI are public. Usage always requires a valid key, including in development mode.

Keep a shared service key in your backend environment or secret store. Your frontend calls your own backend, which authenticates its user and calls PaperSignal. Do not embed the shared key in browser bundles or mobile binaries. Consumers need neither the Mistral credential nor the service's admin token.

Isolation is **per key**, not per end user. A key can read/delete only its own jobs. Another key receives 404 for individual job/batch access; lists and multi-ID responses omit inaccessible jobs. When multiple users share your backend key, enforce user-to-job access in your backend.

Open mode (`REQUIRE_API_KEY=false`) permits anonymous operations with no ownership filter, including access to existing owned jobs. Never use open mode for a shared deployment. A replacement key is a new owner and cannot access the original key's jobs. Retrieve required results before revocation; there is no ownership-transfer or key-rotation API.

## 4. Endpoint inventory

Client-key authentication applies in service mode. Admin operations use only `X-Admin-Token`.

| Method and path | Auth | Success | Purpose |
|---|---|---|---|
| `GET /api/health` | Public | 200 object | Configuration and upload limits |
| `POST /api/v1/extractions` | Client key | 202 submission | Send one or more PDFs with one schema |
| `GET /api/v1/extractions/{extraction_id}` | Client key | 200 document array | Status and results for every document |
| `DELETE /api/v1/extractions/{extraction_id}` | Client key | 204 empty | Delete the PDFs and their results |
| `GET /api/v1/account` | Client key | 200 usage | Monthly quota and request limit |
| `POST /api/v1/keys` | Admin token | 201 creation | Issue a client key |

## 5. Health and limits

`GET /api/health` needs no body, parameters or key. Observed AWS response:

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

These upload values also match source defaults; recheck health because settings can change. Backend MB limits use 1,048,576 bytes per MB. Effective capacity is also restricted by the reverse proxy, which health does not report. Checked-in Caddy limits the whole request to `210MB`; an older runbook example uses `60MB`. The live proxy limit was not measured. A 500 MB backend batch allowance does not establish that a 500 MB request will pass the proxy.

Other source defaults, not exposed by health: 10 worker threads, 100 running-plus-queued jobs (`MAX_PENDING_JOBS`), and new-key defaults of 60 requests/minute and 1,000 documents/month. These are configuration values, not measured throughput or an SLA. Each key's actual limits are available from usage.

## 6. Submit one PDF or a batch

`POST /api/v1/extractions` accepts multipart form data:

| Field | Required | Value |
|---|---|---|
| `file` | Yes | One PDF file part, MIME type `application/pdf` |
| `output_template` | Yes | JSON Schema serialized as text, 2-12,000 characters |
| `ocr_mode` | No | `auto` (default), `always`, or `never` |

Send actual file bytes, not a URL or base64 JSON. Let the HTTP client set the multipart Content-Type and boundary. There is no custom instruction request field; describe required fields in the schema.

The 202 response contains an `extraction_id` and one entry per document, each with `status: "queued"`, `progress: 0`, `stage: "Queued"` and `result: null`. It is not the extraction result. File signature, emptiness, readability, password protection, size and page-count errors return 400. Schema/form errors return 422.

**Repeat `files` for every PDF**, not `file` or `files[]`. One schema applies to the entire batch; each PDF has a separate result. File-count, schema and quota errors reject the request. Too much combined data returns 413. Quota is prechecked against all submitted files, including files that might later prove invalid.

Illustrative abbreviated batch response for two submitted files; job fields omitted for readability:

```json
{
  "extraction_id": "example-extraction-id",
  "jobs": [
    {"id": "example-job-id", "file_name": "invoice.pdf", "status": "queued", "result": null}
  ],
  "rejected": [
    {"file_name": "broken.pdf", "error": "The uploaded file is not a valid PDF."}
  ],
  "accepted_count": 1,
  "rejected_count": 1
}
```

Always inspect both counts and `rejected`. **202 can contain zero accepted jobs.** Do not poll such a batch; its ID has no stored jobs and lookup returns 404. Queue saturation during a batch appears as per-file rejections, whereas a full queue on single submission returns 429 without Retry-After.

Batch acceptance is not transactional: an unexpected failure after some jobs were enqueued can leave accepted work despite an unusable response. Uploads have no idempotency support; do not blindly replay them after timeouts or 5xx responses.

### cURL examples

These use Bash syntax. For Windows PowerShell, use the supplied Python/Node clients or Postman instead of Bash line continuations. Privately set `PAPERSIGNAL_API_KEY`; the schema file is supplied under `examples/integration/`.

```bash
BASE="https://papersignal.duckdns.org"

curl --fail-with-body "$BASE/api/v1/account" \
  -H "X-API-Key: $PAPERSIGNAL_API_KEY"

curl --fail-with-body "$BASE/api/v1/extractions" \
  -H "X-API-Key: $PAPERSIGNAL_API_KEY" \
  -F 'file=@invoice.pdf;type=application/pdf' \
  -F 'output_template=<invoice.schema.json' \
  -F 'ocr_mode=auto'

curl --fail-with-body "$BASE/api/v1/extractions" \
  -H "X-API-Key: $PAPERSIGNAL_API_KEY" \
  -F 'files=@invoice-a.pdf;type=application/pdf' \
  -F 'files=@invoice-b.pdf;type=application/pdf' \
  -F 'output_template=<invoice.schema.json'

curl --fail-with-body "$BASE/api/v1/extractions/<extraction_id>" \
  -H "X-API-Key: $PAPERSIGNAL_API_KEY"

curl --fail-with-body "$BASE/api/v1/extractions/<extraction_id>" \
  -H "X-API-Key: $PAPERSIGNAL_API_KEY"
```

`output_template=<invoice.schema.json` sends the file contents as a text field, not a file part.

## 7. JSON Schema and OCR policy

Example `invoice.schema.json`:

```json
{
  "type": "object",
  "properties": {
    "invoiceNumber": {"type": "string", "description": "Invoice identifier printed on the document"},
    "invoiceDate": {"type": "string", "description": "Invoice date, YYYY-MM-DD when available"},
    "totalAmount": {"type": "number"},
    "currency": {"type": "string"}
  }
}
```

Root type must be exactly `object`, with nonempty `properties`. Example data such as `{"invoiceNumber":"INV-123"}` is not a schema and returns 422. Supported types: string, number, integer, boolean, object, array, null. Nested objects must have properties. Maximum depth is 8 below the root and 100 properties per object. Specify array `items`; if omitted they default to string. `$ref`, `allOf`, `anyOf`, `oneOf` and `not` are rejected.

The server makes every declared property required and nullable, then removes extra output keys. Missing/incompatible scalars become null; missing nested objects expand to their declared child keys with null values. Missing/incompatible arrays become null. Prefer one concrete type per field; this is not a complete JSON Schema implementation.

Descriptions and selected constraints (`enum`, `format`, `minimum`, `maximum`, `minLength`, `maxLength`) are forwarded to the model. Local postprocessing checks shape and basic types, **not every constraint or factual correctness**. Consumers must validate totals, dates, enum membership and other business rules. Other schema keywords are not guaranteed to be enforced.

| Mode | Page-reading behavior |
|---|---|
| `auto` | Embedded text first; weak pages use vision, then OCR if vision is insufficient or fails |
| `always` | Force OCR for all pages |
| `never` | Embedded text only; no vision/OCR; fails when no readable text exists |

**All modes still use Mistral for structured extraction.** `never` does not disable external AI processing. Readable digital text is sent to Mistral; vision sends selected rendered page images. OCR currently uploads the complete PDF to Mistral while requesting selected pages. It attempts deletion of that provider upload afterward, but suppresses deletion errors. This implementation does not establish provider retention or data-residency guarantees.

## 8. Polling and result contract

`GET /api/v1/extractions/{extraction_id}` returns an array ordered by creation time and ID, with no wrapper, aggregate status or pagination. It returns 404 if no visible documents remain, including when the extraction belongs to another key. Match records by ID rather than array position.

| Job field | Type and meaning |
|---|---|
| `id`, `extraction_id` | Document ID; the extraction it belongs to |
| `file_name`, `file_size` | Sanitized display name; uploaded bytes |
| `instruction` | Fixed instruction set by the service |
| `output_template` | Submitted schema string, or null for legacy records |
| `ocr_mode`, `schema_mode` | OCR policy; new jobs use `json_schema` |
| `status` | queued, processing, completed, failed |
| `progress`, `stage` | Integer 0-100 and display text, not an ETA |
| `result` | Null before success; extraction object on completion |
| `error`, `failure_code`, `failure_stage` | Failure diagnostics or null |
| `page_count` | Page count or null |
| `python_text_pages`, `ocr_pages` | Embedded-text route count and targeted OCR page count |
| `vision_attempted_pages`, `vision_pages`, `vision_failed_pages` | Vision attempts, sufficient transcripts and fallback counts |
| `text_model`, `vision_model`, `ocr_model` | Configured identifiers or null; top-level values do not prove a model ran |
| `duration_ms` | Worker duration or null; excludes queue wait |
| `created_at`, `updated_at` | ISO-8601 UTC timestamps |

Local file paths and owning key IDs are not returned. Counts are processing diagnostics, not accuracy measures; `never` counts all pages under `python_text_pages`, even empty pages. In `result.document`, unused vision/OCR model identifiers are null.

Illustrative completed `result`, without its surrounding job envelope:

```json
{
  "request": "Extract only the fields defined by the supplied JSON Schema.",
  "data": {"invoiceNumber":"INV-123","invoiceDate":null,"totalAmount":1250,"currency":"INR"},
  "evidence": [{"label":"Invoice number","page":1,"evidence":"Invoice INV-123"}],
  "warnings": ["Invoice date was not found."],
  "document": {
    "page_count":1,"title":null,"author":null,
    "file_name":"invoice.pdf","file_size":24576,
    "ocr_pages":0,"python_text_pages":1,
    "vision_attempted_pages":0,"vision_pages":0,"vision_failed_pages":0,
    "text_sections":1,"text_model":"mistral-small-2603",
    "vision_model":null,"ocr_model":null,
    "schema_mode":"json_schema","duration_ms":5200
  }
}
```

Business values are in `job.result.data`. Evidence pages are one-based or null. Evidence is model-generated and not guaranteed for every field. Warnings can be empty even when business validation is required.

Normal states are queued -> processing -> completed or failed. Both terminal states use progress 100; inspect `status`, not progress alone. Polling a failed job returns HTTP 200.

## 9. Usage and request budgets

`GET /api/v1/account` needs no body or query. Example:

```json
{
  "api_key": {
    "id":"example-key-id","name":"CRM production","key_prefix":"ps_live_ABC123...",
    "rate_limit_per_minute":60,"monthly_document_quota":1000,"documents_this_month":12,
    "created_at":"2026-09-01T08:00:00+00:00",
    "last_used_at":"2026-09-08T08:00:00+00:00","revoked_at":null
  },
  "period":"2026-09","documents_this_month":12,
  "monthly_document_quota":1000,"documents_remaining":988,"rate_limit_per_minute":60
}
```

Accepted documents count at submission, even if processing later fails. Rejected files do not increment document usage; deletion does not refund it. Batch quota precheck nevertheless counts all submitted files. Allowances use calendar-month UTC buckets (`YYYY-MM`), with no carry-over. HTTP 402 represents quota exhaustion, not an implemented payment system.

All authenticated consumer operations, including polling and usage checks, share a sliding 60-second rate window per key. Public health/docs and admin calls do not use that limiter. Start with one poll every 3 seconds (about 20 requests/minute per stream), aggregate batch polling, and coordinate all callers sharing a key. Adjust for lower per-key limits.

Quota checking and increment are separate operations; concurrent uploads can exceed the remaining allowance. Counters are not a strict financial ledger. Internally recorded batch pages can include prepared files rejected by a full queue; page counts are not exposed as usage or used for document quota enforcement.

## 10. Delete and retention

`DELETE /api/v1/extractions/{extraction_id}` removes every PDF in the extraction and its results. Success is 204 with no body. Missing or inaccessible extractions return 404; an extraction with a document still processing returns 409.

```bash
# Run only after saving the result you need.
curl --fail-with-body -X DELETE "$BASE/api/v1/extractions/<extraction_id>" \
  -H "X-API-Key: $PAPERSIGNAL_API_KEY"
```

The route permits queued deletion, but the worker can start between checking and deleting. Treat this as deletion, not guaranteed cancellation; delete only terminal jobs in integrations. There is no raw-PDF download, batch-delete, cancel or restore API. Local deletion does not undo provider processing or remove independent backups.

The application does not schedule retention. Operator cleanup is available, but bulk `cleanup.py` currently scans only the latest 100 jobs and can miss older records. Agree on retention and backup handling with the operator.

## 11. Admin operations

Admin routes require `X-Admin-Token: <ADMIN_TOKEN>` over HTTPS. Never expose this token to consumer frontends. All admin routes return 503 if no server admin token is configured, or 401 for a wrong/missing token when configured.

`POST /api/v1/keys` takes an application/json body:

```json
{"name":"CRM production","rate_limit_per_minute":60,"monthly_document_quota":1000}
```

Name is required, 1-120 characters; whitespace-only is rejected. Request limit is optional integer 1-10,000. Quota is optional integer 1-10,000,000. Omitted/null limits use server defaults. Invalid inputs return 422.

201 returns `{"key":"<NEW_RAW_KEY>","api_key":{...}}`, where metadata has the fields shown inside usage above. The raw `ps_live_` key is returned once and stored only as a SHA-256 hash. Save it securely when issued.

AWS operator CLI alternative, using the server's configured data directory:

```bash
cd /home/ubuntu/Paper-Signal/backend
./.venv/bin/python manage_keys.py create "CRM production" --rate-limit 60 --quota 1000
./.venv/bin/python manage_keys.py list
./.venv/bin/python manage_keys.py revoke <key_id>
```

## 12. Errors and retries

Explicit API errors generally use `{"detail":"message"}`. FastAPI input-validation errors use a detail array with `loc`, `msg`, `type`, and possibly rejected input. Proxy/unhandled errors may be text or HTML. Avoid indiscriminately logging potentially sensitive error bodies.

| HTTP status | Meaning and action |
|---|---|
| 200 | Read succeeded; still inspect job status |
| 201 | Key created; save its one-time raw value |
| 202 | Submission accepted; inspect rejections then poll |
| 204 | Delete/revoke succeeded; do not parse JSON |
| 400 | Single PDF invalid, empty, protected, corrupt, oversized or over page limit |
| 401 | Missing, invalid or revoked credential; correct authentication |
| 402 | Monthly quota precheck failed; reduce batch or contact operator |
| 404 | Missing/inaccessible job, batch or admin key |
| 409 | Processing job deletion or repeated key revocation |
| 413 | Combined batch/proxy request limit; reduce request size |
| 422 | Invalid/missing schema, form, query, OCR enum or admin fields |
| 429 | Rate limit or single-upload queue saturation; wait and back off |
| 503 | AI configuration missing, admin disabled, or infrastructure unavailable |
| 500, 502, 504 | Unexpected backend/proxy failure; upload may already be accepted |

Rate-limit 429 includes `Retry-After` in seconds; queue-full 429 does not. Retry safe reads with bounded backoff and a deadline. Confirmed rate-limit/queue rejection can be retried deliberately. Never automatically replay uploads after an ambiguous timeout or 5xx: no idempotency/deduplication exists, so duplicate work consumes quota. Persist IDs immediately; reconcile uncertain submissions using recent jobs and operator support. Filename alone is not unique.

Failed jobs use `PDF_PROCESSING_ERROR` for PDF processing failure, `AI_EXTRACTION_ERROR` for an AI failure or absent readable text, and `PROCESSING_ERROR` for other worker errors. Consult `error` and `failure_stage` with the job ID.

A client polling deadline does not cancel server work. Keep the ID and allow later lookup. No guaranteed completion time, webhook, streaming endpoint, synchronous extraction endpoint, URL import or automatic restart recovery exists.

## 13. Browser CORS and backend integration

Server-to-server calls do not need CORS changes. For intentional direct browser use, configure exact browser origins and restart the service. With the pinned settings library, use a JSON-array environment value:

```dotenv
CORS_ORIGINS=["https://papersignal.duckdns.org","https://crm.example.com"]
```

Do not rely on legacy comma-separated examples. Allowed methods are GET, POST, DELETE and OPTIONS. Allowed application headers include Content-Type, X-API-Key and Authorization; cookies/credentials are disabled. `Retry-After` is not exposed to cross-origin JavaScript, and `X-Admin-Token` is not in allowed browser headers. CORS does not protect an exposed shared key.

## 14. Runnable examples and acceptance

See [example instructions](../examples/integration/README.md), [Python](../examples/integration/python_client.py), [Node.js](../examples/integration/node_client.mjs), and [invoice schema](../examples/integration/invoice.schema.json). Both clients upload once, save the returned ID to the console, then use bounded polling with error handling.

Before rollout, use a dedicated key and synthetic PDFs to verify one text PDF, one scan, partial batch rejection, failed-job handling, key isolation, rate/quota responses and deletion in a controlled environment. Confirm effective proxy limits, retention, backups and restart behavior. The current review verified local automated behavior and public live endpoints, not live extraction accuracy or capacity.
