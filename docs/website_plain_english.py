"""Plain-English page copy for the developer documentation website."""
import json

COPY = {
'overview': ('Build with PaperSignal', 'Read a PDF and get the fields your application needs as JSON.', '''
## What PaperSignal does
PaperSignal reads a PDF and returns the fields you ask for. For example, your invoice app can ask for the invoice number, date, amount and currency.

Your app can call the API directly. You do not need to use the PaperSignal upload screen or connect to its database.

## What you need
- A client API key from the service owner.
- A PDF file.
- A JSON Schema: a list of the fields you want and their data types.
- A backend that can send HTTP requests and check the result later.

## How it works
1. Send the PDF and your schema to PaperSignal.
2. Save the job ID from the response. A job is the saved task for one PDF.
3. Check the job every few seconds until it finishes.
4. Read result.data, check the values, and save them in your app.

## Start here
[Follow the quick start](/documentation/quickstart), [see the latest API test results](/documentation/test-results), or [download a complete Python or Node.js example](/documentation/examples).

## Keep the key on your backend
Your frontend should call your own backend. Your backend sends the API key to PaperSignal. Do not put a shared API key in browser or mobile code.

## Before production use
The current service runs as one application instance. Work may stop after a restart and does not restart automatically. PDF text, and sometimes page images or the full PDF, are sent to Mistral for AI processing. Read [service limits](/documentation/operations) before using business documents.
'''),
'quickstart': ('Your first extraction', 'Send a sample PDF, check its progress, and read the extracted data.', '''
## 1 Get a client key
Ask the service owner for a key for your application. Save it as PAPERSIGNAL_API_KEY in your backend environment. Do not put a real key in code you share.

## 2 Choose the fields
Save this as invoice.schema.json beside your PDF. The schema below asks for four invoice fields.
```json
__SCHEMA__
```
## 3 Send the PDF
Use one of the code examples above. Replace invoice.pdf with your file. The cURL example uses Bash. The short Python example needs the requests package; the full downloadable Python client needs no extra package.

The server returns HTTP 202 and a job ID. This means the file was accepted. It does not mean extraction has finished. Save the id now.

## 4 Check the result
Replace JOB_ID with the returned id. Repeat this request about every three seconds for one job, while staying within your key's request limit.
```bash
curl --fail-with-body "https://papersignal.duckdns.org/api/jobs/JOB_ID" \\
  -H "X-API-Key: $PAPERSIGNAL_API_KEY"
```
| status | What to do |
|---|---|
| queued | The job is waiting. Check again later. |
| processing | The job is running. Check again later. |
| completed | Read result.data. |
| failed | Read error, failure_code and failure_stage. |

Set a time limit in your app. If you stop waiting, keep the job ID so you can check again later. Stopping your request does not stop the server job.

## 5 Use the data
```json
{"invoiceNumber":"INV-123","invoiceDate":null,"totalAmount":1250,"currency":"INR"}
```
This is an example of result.data. null means the value was not found or did not match the expected type. Check important values before saving or using them.

## Next steps
[Download a full upload-and-check client](/documentation/examples). For several PDFs, use [batch upload](/documentation/batch-upload). Save your results before [deleting a job](/documentation/delete-job).
'''),
'authentication': ('Authentication', 'Send your client API key with each protected request.', '''
## Send the key
Use either header:
```http
X-API-Key: <YOUR_CLIENT_API_KEY>
```
```http
Authorization: Bearer <YOUR_CLIENT_API_KEY>
```
If both are present, a nonempty X-API-Key is used. A wrong, missing or revoked key returns 401. Revoked means the service owner has disabled the key.

## Public pages
Health, Swagger and OpenAPI do not need a key. All consumer APIs need a key when service key mode is on. The usage API always needs a key.

## Which jobs can a key access
A key can read and delete only the jobs created with that key. Another key gets 404 for a job or batch. Lists leave out jobs belonging to other keys.

If many users share one backend key, your backend must check which user owns each job. PaperSignal does not know your app's individual users.

## Where to store keys
Keep shared keys on your backend, not in browser code, mobile code or a shared repository. Use HTTPS. The client key is different from the Mistral key and the admin token; do not give those to API users.

## Replacing a key
A new key cannot read the old key's jobs. Save needed results before disabling the old key. There is no API to move jobs between keys.

## Development mode
With REQUIRE_API_KEY=false, anonymous requests have no job-owner filter. This can expose existing jobs. Keep REQUIRE_API_KEY=true on a shared server.
'''),
'health': ('Service health', 'Check whether the API responds and read its configured limits.', '''
## Request
No key, body or query parameters are needed.

## Response
The server returns HTTP 200 with an object like this. Values can change when the owner changes the settings.
```json
{"status":"ok","ai_configured":true,"require_api_key":true,
 "max_upload_mb":200,"max_pdf_pages":40,"max_batch_files":10,
 "max_batch_total_mb":500,"text_model":"mistral-small-2603",
 "vision_model":"mistral-small-2603","ocr_model":"mistral-ocr-4-0"}
```
## What the fields mean
| Field | Meaning |
|---|---|
| status | ok means this API request succeeded. |
| ai_configured | AI keys are saved in settings. This does not prove that AI extraction works. |
| require_api_key | Whether protected routes require a client key. |
| max_upload_mb | Maximum size of one PDF. |
| max_pdf_pages | Maximum number of pages in one PDF. |
| max_batch_files | Maximum number of files in one batch. |
| max_batch_total_mb | Maximum combined file size allowed by the backend. |
| text_model, vision_model, ocr_model | Model names in the server settings. |

## A limit outside this response
The web server in front of the API may allow a smaller request. The checked-in Caddy config allows 210MB per request, while the backend reports 500 MB per batch. The current live proxy limit has not been measured. Ask the owner before offering large uploads.
'''),
'upload': ('Submit a PDF', 'Send one PDF and the fields you want. Get a job ID to check later.', '''
## Request body
Use multipart/form-data. Let your HTTP library set the Content-Type and boundary.
| Field | Required | What to send |
|---|---|---|
| file | Yes | One PDF file, with type application/pdf. |
| output_template | Yes | JSON Schema as text, 2-12,000 characters. |
| ocr_mode | No | auto, always or never. Default: auto. |

Send file bytes, not a file URL or base64 JSON. There is no custom instruction field. Describe the required fields in your schema.

## Response
HTTP 202 returns a job. result is null because work has not finished. batch_id is null for this single-file API. The complete example below uses a schema with only totalAmount.
```json
__JOB__
```
## What to do next
Save id in your app and [check the job](/documentation/get-job). The result will be in result.data when status is completed.

## Common errors
400: the PDF is empty, invalid, protected, too large or has too many pages. 422: a required field or schema is missing or invalid. 401: the key is invalid. 402: the monthly document limit is reached. 429: too many requests or the work queue is full. 503: AI keys are not configured.

## If you lose the response
Do not send the same PDF again immediately. It may already be accepted. The API does not detect duplicate uploads, so another request can use more quota. Check recent jobs or contact the owner first.
'''),
'batch-upload': ('Submit a batch', 'Send several PDFs with one schema. Get one result for each accepted file.', '''
## Request body
Use multipart/form-data. Repeat the field named files once for each PDF. Do not use file or files[].
| Field | Required | What to send |
|---|---|---|
| files | Yes | One or more PDF file parts. |
| output_template | Yes | One JSON Schema text field, 2-12,000 characters. |
| ocr_mode | No | auto, always or never. Default: auto. |

The same schema is used for every file. A batch does not combine the PDFs into one result.

## Response
HTTP 202 returns accepted jobs and rejected files. This example leaves out some job fields to keep it short.
```json
{"batch_id":"example-batch-id","accepted_count":1,"rejected_count":1,
 "jobs":[{"id":"example-job-id","status":"queued","result":null}],
 "rejected":[{"file_name":"bad.pdf","error":"The uploaded file is not a valid PDF."}]}
```
## Check both counts
Always read accepted_count, rejected_count and rejected. A 202 response can have zero accepted jobs. In that case, do not check the batch later: it has no saved jobs and batch lookup returns 404.

If the work queue becomes full, affected files appear in rejected. Valid files can still be accepted while invalid files are rejected.

## Limits and errors
Too many files or an invalid schema returns 422. Too much combined data returns 413. The monthly quota check counts all submitted files before validation, but only accepted documents are added to usage.

## Next step
Save batch_id and the accepted job IDs. [Check the batch](/documentation/get-batch) until all accepted jobs finish. A server error may happen after some files have been accepted, so do not automatically send the whole batch again.
'''),
'get-job': ('Retrieve a job', 'Check one job and read its result using the key that created it.', '''
## Path parameter
| Parameter | Required | Meaning |
|---|---|---|
| job_id | Yes | The id returned when you uploaded the PDF. |

Replace {job_id} in the URL with the real ID.

## Response
HTTP 200 returns one [job object](/documentation/results). result is null before success. This short example leaves out other job fields and result metadata.
```json
{"id":"example-job-id","status":"completed","progress":100,
 "result":{"data":{"totalAmount":1250},"evidence":[],"warnings":[]}}
```
## Check status
queued means waiting; processing means running. completed means the data is ready. failed means extraction did not succeed. A failed job still returns HTTP 200, so your app must check status.

## How often to check
Start with one check every three seconds. All requests using the same key share its rate limit. If you get 429, wait for Retry-After before checking again. Set a deadline and keep the job ID if you stop waiting.

## Errors
404 means the job does not exist or belongs to another key. 401 means the key is invalid. 429 means the request limit was reached.
'''),
'get-batch': ('Retrieve a batch', 'Check all jobs in a batch with one request.', '''
## Path parameter
| Parameter | Required | Meaning |
|---|---|---|
| batch_id | Yes | The batch_id returned by batch upload. |

## Response
HTTP 200 returns a list of job objects. There is no outer batch object or overall batch status. This example leaves out other job fields.
```json
[{"id":"job-a","status":"completed","result":{"data":{"totalAmount":1250}}},
 {"id":"job-b","status":"processing","result":null}]
```
## When to stop checking
Keep checking while an expected job is queued or processing. Stop when every expected job is completed or failed. One failed job does not mean the other jobs failed.

Jobs are ordered by creation time, then ID. Use each job's ID to match it to your app's records; do not rely on list position.

## Missing batch
404 means no jobs in this batch are visible to your key. This can happen for an unknown batch, another key's batch, an all-rejected upload, or a batch whose jobs were deleted. Save the accepted job IDs and handle missing jobs separately.
'''),
'get-many': ('Retrieve selected jobs', 'Check up to 50 job IDs in one request.', '''
## Query parameter
| Parameter | Required | Meaning |
|---|---|---|
| ids | Yes | Job IDs separated by commas, such as id1,id2. |

Send at least one nonempty ID and at most 50 nonempty IDs.

## Response
HTTP 200 returns a list of full job objects. Repeated IDs appear once. The response follows the order of the first occurrence of each ID.

Unknown IDs and jobs belonging to other keys are left out. If no jobs are visible, the result is:
```json
[]
```
An empty list is not proof that work finished. Compare the returned IDs with the IDs you requested.

## Errors
422 means ids is missing, empty or has more than 50 IDs. A wrong key returns 401. Too many requests returns 429.
'''),
'list-jobs': ('List recent jobs', 'Get the most recent jobs created with your key.', '''
## Query parameter
| Parameter | Required | Meaning |
|---|---|---|
| limit | No | Number of jobs to return. Default: 20. |

Values below 1 are changed to 1. Values above 100 are changed to 100. The value must be an integer.

## Response
HTTP 200 returns a list of full job objects, newest first. A key with no jobs receives an empty list.
```json
[]
```
There is no next-page token, offset or total count. Save job IDs in your own database if you need complete history.

## Finding an uncertain upload
Use this list to help check an upload whose response was lost. A filename is not a unique ID. Check the time and your own records, or ask the service owner, before uploading again.
'''),
'delete-job': ('Delete a job', 'Remove a saved PDF and its result after you have saved what your app needs.', '''
## Path parameter
| Parameter | Required | Meaning |
|---|---|---|
| job_id | Yes | The ID of a job owned by your key. |

## Response
HTTP 204 means deletion succeeded. The response has no body, so do not try to read JSON from it. The local PDF and job/result record are removed. There is no restore API.

## When to delete
Delete only completed or failed jobs in your integration. A processing job returns 409. Although the code allows deleting queued jobs, a worker can start at the same time, so this is not a reliable way to cancel work.

## Errors
404 means the job is missing or belongs to another key. 409 means it was processing when checked. 401 means the key is invalid.

## Data retention
Deletion does not refund document quota. It does not undo AI processing or remove independent backups. There is no PDF-download, batch-delete or cancel API.

The app does not automatically schedule deletion. The current bulk cleanup script looks only at the latest 100 jobs and can miss older data. Agree on a retention policy with the service owner.
'''),
'usage': ('Usage and quotas', 'Check how many documents your key has used this month and how many remain.', '''
## Request
Send your client key. No body or query parameters are needed. This endpoint needs a key even when development mode allows anonymous calls.

## Response
```json
{"api_key":{"id":"example-key-id","name":"CRM production",
 "key_prefix":"ps_live_ABC123...","rate_limit_per_minute":60,
 "monthly_document_quota":1000,"documents_this_month":12,
 "created_at":"2026-09-01T08:00:00+00:00",
 "last_used_at":"2026-09-08T08:00:00+00:00","revoked_at":null},
 "period":"2026-09","documents_this_month":12,
 "monthly_document_quota":1000,"documents_remaining":988,
 "rate_limit_per_minute":60}
```
## Document limit
An accepted document uses one unit when uploaded, even if extraction later fails. Rejected files do not add usage. Deleting a job does not refund usage.

The period is a calendar month in UTC, shown as YYYY-MM. The next month starts a new count. Unused allowance does not carry over. A 402 response means the requested upload would exceed the monthly limit; it is not a payment page.

## Request limit
Uploads, status checks, usage checks and deletes share one limit for the same key. At one check every three seconds, one polling stream uses about 20 requests per minute. Use batch checks for many jobs.

429 from the rate limiter includes Retry-After in seconds. Public health/docs and admin calls do not use this client rate limit.

## Current limitations
The quota check and usage update happen separately. Simultaneous uploads can exceed the intended limit. Batch page counters can also include files rejected by a full queue. Do not use these counters as an exact billing system without fixes.
'''),
'create-key': ('Create an API key', 'Service owners use this API to give another application its own key.', '''
## Admin access
Use X-Admin-Token, not a client API key. Never send the admin token to end users.

## Request body
Use Content-Type: application/json.
| Field | Required | Allowed value |
|---|---|---|
| name | Yes | 1-120 characters. Spaces alone are not allowed. |
| rate_limit_per_minute | No | Integer from 1 to 10,000. |
| monthly_document_quota | No | Integer from 1 to 10,000,000. |

If a limit is missing or null, the server uses its default for new keys.
```json
{"name":"CRM production","rate_limit_per_minute":60,"monthly_document_quota":1000}
```
## Save the key now
HTTP 201 returns key and api_key. key is the full secret value and is shown only once. api_key contains the ID, name, display prefix, limits, usage and timestamps.
```json
{"key":"<NEW_RAW_KEY>","api_key":{"id":"example-key-id",
 "name":"CRM production","key_prefix":"ps_live_ABC123...",
 "rate_limit_per_minute":60,"monthly_document_quota":1000,
 "documents_this_month":0,"created_at":"2026-09-08T08:00:00+00:00",
 "last_used_at":null,"revoked_at":null}}
```
The server stores a hash, not the full key. You cannot retrieve a lost key. A new key cannot access jobs created by an older key.

## Errors
401: wrong or missing admin token. 503: admin access is not configured. 422: invalid input. There is no API to change an existing key's quota or move its jobs to another key.
'''),
'list-keys': ('List API keys', 'Service owners can view issued keys and their current-month usage.', '''
## Request
Send X-Admin-Token. No body or query parameters are needed.

## Response
HTTP 200 returns key records, newest first. Disabled keys are included. An empty list means no keys have been issued.
```json
[]
```
Each record has id, name, key_prefix, rate_limit_per_minute, monthly_document_quota, documents_this_month, created_at, last_used_at and revoked_at. The full secret key is never returned.

Use the id when you need to disable a key. key_prefix is only a short label for display. There is no pagination.

## Client usage
An ordinary API user should call [GET /api/usage](/documentation/usage) to see their own usage. A client key cannot list other keys.

## Errors
401 means wrong or missing admin token. 503 means ADMIN_TOKEN is not configured on the server.
'''),
'revoke-key': ('Revoke an API key', 'Disable a client key so it cannot make more API requests.', '''
## Request
Send X-Admin-Token. Replace {key_id} with the ID from key creation or key listing. Do not put the full secret key or display prefix in the URL.

## Response
HTTP 204 has no body and means the key was disabled. Future requests with that key return 401.

This does not cancel jobs already accepted, delete files, or move jobs to another key.

## Errors
404: unknown key ID. 409: the key is already disabled. 401: wrong or missing admin token. 503: admin access is not configured.

## Replacing a key
Save needed results before disabling the old key. A new key cannot read the old key's jobs. There is no API to re-enable a key, rotate it while preserving its owner ID, or transfer its jobs.
'''),
'schema': ('Schemas and OCR', 'Choose the output fields and tell the service how to read PDF pages.', '''
## What is a JSON Schema
A JSON Schema describes the field names and value types your app expects. Send it as text in output_template.
```json
__SCHEMA__
```
Do not send example data such as {"totalAmount":42}. The root must have type object and a nonempty properties object.

## Allowed types and limits
Use string, number, integer, boolean, object, array or null. Every nested object needs at least one property. Each object can have up to 100 properties, with up to 8 levels below the root.

For arrays, set items to describe each value. If items is missing, it defaults to string. Prefer one concrete type per field. $ref, allOf, anyOf, oneOf and not are not supported.

## Missing and extra values
All declared fields appear in the output. Missing values or values with the wrong basic type become null. Extra output keys are removed. Missing nested objects become their declared child fields with null values. A missing or wrong-type array becomes null.

## Check business rules yourself
The model receives descriptions and selected constraints such as enum, format, minimum, maximum, minLength and maxLength. The local output check enforces field shape and basic types, not every schema rule or factual accuracy. Your app must check dates, amounts and allowed values before acting on them.

## OCR modes
OCR means reading text from page images.
| Mode | What happens |
|---|---|
| auto | Read embedded text first. Try vision for weak pages, then OCR if needed. |
| always | Use OCR for every page. |
| never | Read only embedded text. Image-only PDFs fail if they contain no readable text. |

## Where the document goes
All modes still use Mistral to extract the final fields. never does not turn off AI. Digital text is sent to Mistral; vision sends selected page images. OCR currently uploads the full PDF and asks for selected pages. The code tries to delete that provider upload, but a failed deletion is not reported to the user. Provider retention terms were not checked in this review.
'''),
'results': ('Jobs and results', 'Understand status, extracted data and the extra details returned with each job.', '''
## Job status
| Status | Meaning |
|---|---|
| queued | Waiting for a worker. |
| processing | Running. |
| completed | Result is ready. |
| failed | Work did not succeed. Read the error details. |

Both completed and failed can have progress 100. HTTP 200 on a status request only means the lookup worked.

## Job fields
| Field | Meaning |
|---|---|
| id, batch_id | Job ID and optional batch ID. |
| file_name, file_size | Safe display filename and size in bytes. |
| instruction | The fixed extraction instruction used by the server. |
| output_template | The submitted schema as a string; may be null for old jobs. |
| ocr_mode, schema_mode | Page-reading policy and schema mode. New jobs use json_schema. |
| status, progress, stage | State, progress from 0-100, and a human-readable stage. |
| result | null before success; extracted result after completion. |
| error, failure_code, failure_stage | Failure details or null. |
| page_count | Number of pages, or null. |
| python_text_pages, ocr_pages | Page counts for embedded-text and OCR routes. |
| vision_attempted_pages, vision_pages, vision_failed_pages | Vision attempts, successful reads and fallbacks. |
| text_model, vision_model, ocr_model | Configured model names. A name here does not prove it was used. |
| duration_ms | Worker time in milliseconds; excludes time waiting in the queue. |
| created_at, updated_at | UTC timestamps in ISO-8601 format. |

The response does not include the local file path or owning key ID. Page counts are processing details, not accuracy scores. In never mode, python_text_pages includes empty pages too.

## Inside result
| Field | Meaning |
|---|---|
| data | The business values requested by your schema. |
| evidence | Supporting text with label, page and evidence fields. Page is one-based or null. |
| warnings | Messages from extraction. May be empty. |
| request | The extraction instruction. |
| document | File metadata, page-reading counts, model names, section count and duration. |

Use result.data in your app. Evidence is generated by the model and may not cover every field. Empty warnings do not prove the values are correct.

## Which lookup to use
Use [one job](/documentation/get-job), [one batch](/documentation/get-batch), or [up to 50 IDs](/documentation/get-many). Use [recent jobs](/documentation/list-jobs) for a short history. Save job IDs in your own database for complete tracking.
'''),
'errors': ('Errors and retries', 'Check HTTP errors and job failures separately. Retry only when it is safe.', '''
## HTTP status codes
| Code | Meaning and next step |
|---|---|
| 200 | Read succeeded. Still check the job status. |
| 201 | A key was created. Save the one-time key. |
| 202 | Upload accepted. Check the job later. |
| 204 | Delete or revoke succeeded. There is no JSON body. |
| 400 | Invalid, empty, protected, oversized or over-page-limit PDF. Fix the file. |
| 401 | Wrong, missing or disabled key/token. Check credentials. |
| 402 | Monthly document limit reached. Contact the owner. |
| 404 | Item is missing or belongs to another key. Check the ID and key. |
| 409 | Job is processing, or the key was already disabled. |
| 413 | Combined upload or proxy size limit exceeded. Send less data. |
| 422 | Missing or invalid form, schema, OCR mode, query or admin input. |
| 429 | Too many requests or the single-upload queue is full. Wait. |
| 503 | AI/admin configuration is missing, or the service is unavailable. |
| 500, 502, 504 | Server or proxy error. The upload may already be accepted. |

## Error body
Most explicit API errors return an object like this:
```json
{"detail":"Send your key in the X-API-Key header."}
```
Input-validation errors may put a list in detail instead of a string. Proxy errors may return HTML or text. Do not assume every error body is JSON, and avoid logging sensitive inputs.

## Job failures
A status lookup can return HTTP 200 with status failed.
| failure_code | Meaning |
|---|---|
| PDF_PROCESSING_ERROR | The worker could not read or process the PDF. |
| AI_EXTRACTION_ERROR | The AI call failed, or no readable text was found. |
| PROCESSING_ERROR | Another worker error occurred. |

Read error and failure_stage, and keep the job ID for support. [See recent test results](/documentation/test-results) for known observed failures.

## Retrying requests
Safe read requests can be retried with a delay and a time limit. A rate-limit 429 includes Retry-After in seconds; a queue-full 429 does not. For example, if Retry-After is 5, wait at least five seconds.

Do not automatically repeat uploads after a timeout, lost response or 5xx. The first upload may already be running, and the service does not remove duplicates. Another upload can use more quota. Check recent jobs or ask the owner first.

## Waiting too long
Use a deadline in your app. If the deadline passes, keep the ID and allow later lookup. Your timeout does not cancel the job, and the service does not promise a fixed completion time.
'''),
'cors': ('Browser integration', 'Call PaperSignal from your backend to keep shared keys private.', '''
## Recommended setup
Your frontend sends the PDF to your backend. Your backend checks its user, then calls PaperSignal with the client key. Server-to-server calls do not need browser CORS changes.

## Direct browser calls
CORS is the browser rule that controls calls between different website origins. If you intentionally call the API from a browser, the owner must allow that browser's exact origin and restart the service.
```dotenv
CORS_ORIGINS=["https://papersignal.duckdns.org","https://crm.example.com"]
```
Use this JSON-array format with the current settings library. Do not rely on older comma-separated examples.

## Supported browser requests
Allowed methods are GET, POST, DELETE and OPTIONS. Allowed application headers include Content-Type, X-API-Key and Authorization. Cookies are not enabled. X-Admin-Token is not in the allowed browser headers.

## Reading Retry-After
The server does not expose Retry-After to cross-origin JavaScript. Browser code may not be able to read it even though the HTTP response has it. A backend client can read it normally.

## CORS is not authentication
Allowing an origin does not make a shared key safe to expose. Anyone who gets that key can use its allowed APIs and access its jobs.
'''),
'examples': ('Complete client examples', 'Download a working starting point for uploads and status checks.', '''
## Download the files
- [Python client](/documentation-assets/python_client.py): Python 3.11 or later; no extra packages.
- [Node.js client](/documentation-assets/node_client.mjs): Node.js 22 or later; no extra packages.
- [Invoice schema](/documentation-assets/invoice.schema.json): example field names and types.

Save the client and invoice.schema.json in the same folder. Both clients upload once, print the job ID, and check status until success, failure or a ten-minute deadline.

## Set your key privately
These are PowerShell examples. Replace the placeholder with your own client key in your private environment.
```powershell
$env:PAPERSIGNAL_API_KEY = '<YOUR_CLIENT_KEY>'
$env:PAPERSIGNAL_BASE_URL = 'https://papersignal.duckdns.org'
```
## Run a client
```powershell
python python_client.py 'C:\\Documents\\invoice.pdf'
node node_client.mjs 'C:\\Documents\\invoice.pdf'
```
This sends a real upload and uses your document quota. Start with a small sample file. The examples hold the whole PDF in memory; use a streaming upload library for large documents.

## Use it in your app
Put uploads and status checks in your backend or background worker. Save the returned ID against your business record and user. Check result.data before saving it or triggering an action.

## Error handling
The examples retry some read errors, but never automatically repeat an upload. They do not delete results automatically. If the waiting deadline passes, the job may still be running. Keep its ID and check later.

## Tests
The examples passed local tests for file-upload format, successful status checks, rate-limit responses, failed jobs and invalid authentication. These use controlled HTTP responses. The separate [API test report](/documentation/test-results) explains real-provider and AWS tests.
'''),
'operations': ('Service limits and data handling', 'Know the current limits before you depend on this service.', '''
## Current design
PaperSignal uses one API instance, local PDF storage, SQLite databases and an in-memory work queue. An in-memory queue is stored in the running process, so accepted jobs may be left unfinished after a crash or restart. The code does not automatically resume them.

## Recovery and scale
For reliable restart recovery, use a durable queue and a way to resume interrupted jobs. For several API instances, use shared file storage, a shared database and a shared rate limiter. These changes were not made as part of this documentation task.

## Upload limits
Health reports the backend's configured limits. A proxy can reject smaller requests first. Verify the actual request limit before allowing large uploads. Queue capacity includes both running and waiting jobs; it is not a throughput promise.

## Duplicate uploads and quotas
The API has no idempotency key, so it does not identify duplicate upload requests. A lost response can lead to duplicate work if your app retries.

Quota checking and usage updates are separate. Simultaneous uploads may exceed a quota. Internal batch page counts may include queue-rejected files. Fix these before using the counters for exact billing.

## Keys and deletion
A new key cannot read an old key's jobs. Plan how to save results before replacing a key. Delete only completed or failed jobs; queued deletion is not reliable cancellation.

The current bulk cleanup script scans only the latest 100 jobs. Older data can be missed. Set and verify a retention schedule instead of assuming files disappear automatically.

## External AI processing
All modes send readable text to Mistral. Vision sends selected page images. OCR uploads the full PDF and requests selected pages, then tries to delete the provider file. AWS hosting does not mean all document processing stays inside AWS. Confirm provider data handling and retention before sending business documents.

## What has been tested
See the [dated API test report](/documentation/test-results). It separates AWS tests, local real-AI tests and tests with controlled responses. Load capacity, large proxy uploads, restart recovery and provider data-retention terms have not been verified.
'''),
}


def apply_plain_english(pages, compile_blocks, schema, job):
    for page in pages:
        if page['id'] not in COPY: raise ValueError('Missing plain-English page: '+page['id'])
        title,summary,body=COPY[page['id']]
        body=body.replace('__SCHEMA__',schema).replace('__JOB__',job)
        page.update(title=title,summary=summary,search=body,blocks=compile_blocks(body))
