# PaperSignal service integration assessment

Prepared for application management and the integration team. Review date: 8 September 2026. Deployed API version: 0.1.0.

**Follow-up test update:** the API design supports integration, but real extraction is currently failing. AWS checks passed for upload acceptance, authentication and job management, while four expected successful extraction cases failed. See [API_TEST_RESULTS.md](API_TEST_RESULTS.md) for the current decision evidence; do not treat the earlier architecture assessment as a successful extraction check.

## Decision

**Yes. PaperSignal can be used by another application as a PDF extraction service.** HTTPS APIs support PDF upload, schema-based field extraction, processing status, JSON results, usage reporting and document deletion. The consuming application can use its own interface and call PaperSignal from its backend with a dedicated API key.

This supports a controlled integration on the current single-instance architecture. The review does not certify high availability, strict billing enforcement or extraction accuracy. A live authenticated document test remains necessary before production onboarding.

## Verification evidence

| Check | Result |
|---|---|
| AWS public health | 200; status ok; AI configured true; API key required true |
| Swagger and OpenAPI | Both 200; deployed contract lists the same 12 business operations as local source |
| Unauthenticated usage | 401, confirming the live authentication boundary for this endpoint |
| Existing local tests | All 44 passed with isolated temporary data; covers API submissions, schemas, authentication, isolation, usage, rate limits, storage and worker behavior |
| Source inspection | Reviewed routes, response models, schema normalization, AI data flow, database, worker queue, key store, cleanup and infrastructure configuration |
| Not verified | Live authenticated extraction, provider credential validity, document accuracy, capacity, active proxy limit, backup/retention schedule or deployed commit identity |

No AWS settings, deployed code or client keys were changed. No customer documents were uploaded. Local tests use controlled/mocked provider behavior and do not establish live AI success.

## Integration design

The operator supplies an HTTPS URL and dedicated client key. The consuming backend defines a JSON Schema, for example invoiceNumber, invoiceDate, totalAmount and currency, then uploads a PDF. It saves the returned job ID against its own business record/user and polls in a background task until completed or failed. On completion, it validates and saves result.data, then displays the result through its own frontend.

The minimum workflow uses POST /api/jobs followed by GET /api/jobs/{job_id}. Multiple files use POST /api/jobs/batch, then GET /api/batches/{batch_id}. A batch applies one schema and returns a separate result per PDF. Always handle per-file rejection; HTTP 202 means accepted, not completed.

Python, Node.js, Java, .NET, PHP or another backend with HTTPS and multipart support can integrate. No shared database or embedded Angular frontend is required. Keep the shared key on the consuming backend, where user-level access is enforced.

## API responsibilities

| API | Purpose |
|---|---|
| GET /api/health | Configuration and configured upload limits |
| POST /api/jobs | Submit one PDF and schema |
| POST /api/jobs/batch | Submit multiple PDFs and report rejections |
| GET /api/jobs/{job_id} | One job's status, result and diagnostics |
| GET /api/batches/{batch_id} | All visible jobs in a batch |
| GET /api/jobs/batch?ids=... | Check up to 50 supplied job IDs |
| GET /api/jobs?limit=20 | List recent jobs, capped at 100 |
| DELETE /api/jobs/{job_id} | Delete a local PDF and job/result |
| GET /api/usage | Monthly documents, remaining quota and request limit |
| POST /api/admin/keys | Operator issues a client key, shown once |
| GET /api/admin/keys | Operator lists key metadata and usage |
| DELETE /api/admin/keys/{key_id} | Operator revokes a client key |

The companion API_INTEGRATION.md defines request fields, response examples, status codes and admin instructions. The handoff includes runnable Python and Node.js examples.

## Input and output agreement

Input is PDF bytes in multipart form data, a required JSON Schema text field named output_template, and optional ocr_mode. Single upload uses file; batch upload repeats files. Invalid, empty, protected, corrupt, oversized and over-page-limit documents are rejected.

JSON Schema defines the field names, nesting and basic types. Output normalization removes extra fields and represents missing/incompatible scalar values as null. It does not guarantee all schema constraints or factual correctness. The consuming application must validate important amounts, dates, identifiers and business rules. Evidence and warnings support review but are not an accuracy guarantee.

Jobs move from queued to processing and then completed or failed. A failed job lookup still returns HTTP 200; inspect its status and failure_code. Progress 100 can represent success or failure. There is no guaranteed completion time or webhook; integrations need a polling deadline and later-lookup handling.

Observed backend limits: 200 MB per PDF, 40 pages per PDF, 10 files per batch and 500 MB combined batch size. Reverse-proxy limits can be lower. Confirm the effective limit before promising these maximums to users.

## Access and data handling

Use separate keys per application/environment. Ownership is tied to the key, so a backend sharing one key across users must enforce user-level isolation itself. A replacement key cannot read the previous key's jobs; plan result retrieval or ownership migration before rotation. Do not turn off key mode on the shared service.

All modes send readable text to Mistral for structured extraction. Vision sends selected rendered pages. OCR currently uploads the complete PDF to Mistral and requests selected pages, then attempts provider-file deletion. Hosting on AWS does not make extraction AWS-only. Provider retention and contractual data-residency terms were not verified.

Local PDFs and results remain until explicit deletion or operator cleanup. Retention is not automatically scheduled. Agree on data handling, backups and deletion before processing business documents.

## Production limitations and decisions

| Finding | Integration impact and next step |
|---|---|
| In-memory queue with no startup recovery | Crash/restart can strand accepted jobs. Add durable work storage and recovery; use polling deadlines and operator reconciliation meanwhile |
| SQLite and local uploads | Current design assumes one API instance and persistent disk. Scale-out needs shared database/storage and coordinated workers |
| No idempotency support | Lost upload responses can lead to duplicate work if retried. Persist IDs and reconcile uncertain submissions |
| Non-atomic quota check and increment | Concurrent uploads can exceed allowance. Add atomic reservation before promising strict financial quotas |
| Batch page accounting includes prepared queue rejections | Internal page totals can overcount. Correct before introducing page billing |
| Job ownership tied to keys | Replacement keys cannot read old jobs. Define a rotation/migration procedure |
| Queued deletion can race worker startup | Consumer should delete terminal jobs only. Guaranteed cancellation needs implementation |
| Cleanup bulk mode scans latest 100 jobs | Older history may be missed. Fix pagination and verify an actual retention schedule |
| Proxy and backend limits differ | Caddy source uses 210MB/request; older runbook uses 60MB; health reports 500 MB batch capacity. Verify and align active limits |
| Authentication uses ordinary OpenAPI headers | Swagger/generated clients need explicit headers. A formal security scheme would improve onboarding |

These findings were documented, not fixed in this task. Prioritize production work against expected traffic, recovery requirements and data sensitivity. No load test was performed.

## Onboarding responsibilities

**Service operator:** issue the dedicated key; maintain HTTPS and key mode; confirm persistent storage, proxy capacity, backups, retention and restart handling; define support ownership and an API change policy.

**Integration team:** secure the key; authorize users; define schemas; persist IDs; handle partial batches, failed jobs, 401/402/429 and timeouts; validate extracted values; save results before deletion. Polling consumes the same request budget as uploads.

**Joint acceptance:** run synthetic text and scanned PDFs using the dedicated test key; verify completion, partial rejection, cross-key isolation and deletion. Exercise rate/quota, uncertain responses and restart recovery in a controlled environment. Live authenticated acceptance remains outstanding.

## Handoff and sources

Base URL: https://papersignal.duckdns.org

Interactive documentation: https://papersignal.duckdns.org/api/docs

OpenAPI import for Postman: https://papersignal.duckdns.org/api/openapi.json

Repository files: docs/API_INTEGRATION.md and examples/integration/README.md, python_client.py, node_client.mjs and invoice.schema.json.

Implementation evidence: backend/app/main.py, models.py, config.py, api_keys.py, database.py, job_service.py, schema_service.py, mistral_service.py, storage.py, backend/cleanup.py, backend/tests/, infra/Caddyfile and infra/papersignal.service. Historical deployment notes were compared with current source and public responses; historical settings are not treated as live facts.
