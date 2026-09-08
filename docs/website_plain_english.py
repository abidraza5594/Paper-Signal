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
2. Save the extraction ID from the response.
3. Check that ID every few seconds until every PDF is finished.
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
curl --fail-with-body "https://papersignal.duckdns.org/api/v1/extractions/JOB_ID" \\
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
[Download a full upload-and-check client](/documentation/examples). For several PDFs, use [batch upload](/documentation/submit). Save your results before [deleting a job](/documentation/delete).
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
'health': ('Check the service is up', 'See whether the service is running and what its current limits are.', '''
## When to use this
Call this before you start, or when something is not working, to confirm the service is reachable. This is the only endpoint that does not need an API key.

## What you get back
```json
{"status":"ok","ai_configured":true,"require_api_key":true,
 "max_upload_mb":200,"max_pdf_pages":40,"max_batch_files":10}
```

| Field | What it tells you |
|---|---|
| status | "ok" means the service is running. |
| require_api_key | true means every other endpoint needs your key. |
| max_batch_files | How many PDFs you can send in one request. |
| max_upload_mb | The largest single PDF you can send. |
| max_pdf_pages | The most pages one PDF can have. |
| ai_configured | false means the owner has not set up the AI provider yet. |

Read the limits from here instead of hard-coding them. The owner can change them.
'''),
'submit': ('Send PDFs for extraction', 'Upload your PDFs and the list of fields you want. You get an ID to check later.', '''
## What this does
You send your PDF files and a JSON Schema saying which fields you want. The service takes the work and answers straight away with an extraction ID.

**The result is not in this response.** Reading a PDF takes 15 to 30 seconds, so the answer comes from [Get the results](/documentation/results-endpoint) using that ID.

## What to send
Use multipart/form-data. Let your HTTP library set the Content-Type and boundary.

| Field | Required | What to send |
|---|---|---|
| files | Yes | Your PDF file. Repeat this field once per PDF. Do not write files[]. |
| output_template | Yes | Your JSON Schema as text, 2-12,000 characters. |
| ocr_mode | No | auto, always or never. Default: auto. |

Send the file bytes, not a link or base64 text.

## What you get back
```json
{"extraction_id":"a1b2c3d4","accepted_count":1,"rejected_count":1,
 "jobs":[{"id":"doc-1","extraction_id":"a1b2c3d4","status":"queued","result":null}],
 "rejected":[{"file_name":"broken.pdf","error":"The uploaded file is not a valid PDF."}]}
```

Save `extraction_id`. That is the only thing you need to get your results.

## A bad file does not spoil the rest
If you send five PDFs and one is damaged, the other four are still processed. The damaged one appears in `rejected` with the reason. Rejected files are not counted against your monthly limit.

Always read `accepted_count`. If it is 0, nothing was accepted and there is nothing to check.

## Common errors
| Code | What happened |
|---|---|
| 401 | Your key is missing, wrong or switched off. |
| 402 | Your monthly document limit is used up. Nothing was processed. |
| 413 | The files together are too large. |
| 422 | Too many files, or your JSON Schema is not valid. |
| 429 | Too many requests. Wait as long as the Retry-After header says. |

## If you do not get a response
Do not send the same PDFs again straight away. They may already have been accepted, and sending them again uses your limit twice. Check first with the extraction ID if you have it.
'''),
'results-endpoint': ('Get the results', 'Check your extraction until it is finished, then read the extracted fields.', '''
## What this does
You give it the extraction ID and it tells you how each document is doing. When a document is finished, its extracted fields are in `result.data`.

Ask again every 2 to 3 seconds until every document says `completed` or `failed`.

## What you get back
```json
[{"id":"doc-1","extraction_id":"a1b2c3d4","file_name":"invoice.pdf",
  "status":"completed","progress":100,
  "result":{"data":{"totalAmount":4500},"evidence":[],"warnings":[]}}]
```

You get a list with one entry per PDF you sent, in the order you sent them.

## The four statuses
| Status | What it means | What to do |
|---|---|---|
| queued | Waiting its turn. | Ask again in a few seconds. |
| processing | Being read now. progress shows how far it is. | Ask again in a few seconds. |
| completed | Finished. | Read result.data. |
| failed | Did not finish. | Read error and failure_code. |

## Reading the result
`result.data` matches your schema exactly. Same field names, same shape. Any field the PDF did not contain comes back as `null`, and anything you did not ask for is removed.

`result.evidence` shows which page each value was found on, so you can check the answer.

## How long it takes
About 15 to 30 seconds per PDF. Two PDFs are read at a time; the rest wait their turn. So ten PDFs take longer than one.

If you stop checking, the work still continues. You can come back to the same ID later.

## If a document failed
The request itself still succeeds with 200. Look at `failure_code` on that document to see whether to try again or fix something. See [When something goes wrong](/documentation/errors).

## You only see your own work
An extraction created with a different key returns 404, as if it does not exist.
'''),
'delete': ('Delete documents and results', 'Remove your uploaded PDFs and their results when you no longer need them.', '''
## What this does
Deletes everything in one extraction: the PDFs you uploaded, the records and the results. This cannot be undone.

## What you get back
| Code | What it means |
|---|---|
| 204 | Deleted. The response is empty, which is normal. |
| 409 | Something is still being read. Wait for it to finish, then try again. |
| 404 | That ID does not exist, or it belongs to a different key. |

## Why you should use it
Your uploaded PDFs stay on the server until something deletes them. Nothing removes them automatically.

If your documents contain private information, call this once your app has saved the fields it needs.
'''),
'account': ('See your usage and limits', 'Check how many documents you have used this month and how many are left.', '''
## What this does
Tells you about your own key: how many documents you may process this month, how many you have used, and how many requests per minute you may make.

## What you get back
```json
{"period":"2026-09","documents_this_month":143,
 "monthly_document_quota":5000,"documents_remaining":4857,
 "rate_limit_per_minute":120}
```

| Field | What it means |
|---|---|
| documents_this_month | Documents accepted so far this calendar month. |
| documents_remaining | How many more you can send before you get 402. |
| rate_limit_per_minute | How many requests you can make in any 60 seconds. |

## Two different limits
**Documents per month** resets at the start of each month. Going over gives you 402 and nothing is processed.

**Requests per minute** is about how fast you call, not how many PDFs you send. Going over gives you 429 with a Retry-After header telling you how long to wait.

A rejected or damaged file does not count against your monthly total.

## Good practice
Check this before sending a large batch so you do not run out halfway. You can also show the remaining count in your own admin screen.
'''),
'create-key': ('Create an API key', 'Service owners use this to give another application its own key.', '''
## Who this is for
Only the person running the service. It needs the `X-Admin-Token` header, which is a different secret from a client API key. A client key cannot call this.

## What to send
```json
{"name":"Acme Corp","rate_limit_per_minute":60,"monthly_document_quota":200}
```
Only `name` is required. The other two fall back to the service defaults.

## What you get back
```json
{"key":"ps_live_xxxxxxxxxxxxxxxxxxxx",
 "api_key":{"id":"key-1","name":"Acme Corp","key_prefix":"ps_live_xxxxxx...",
            "rate_limit_per_minute":60,"monthly_document_quota":200}}
```

**The key is shown once and never again.** Only a scrambled version is stored, so even someone who copies the database cannot use it. If a key is lost, create a new one.

## Give every application its own key
One key per application. Each key sees only its own documents, has its own limits, and can be switched off without affecting anyone else.

## Viewing and switching off keys
These are not available over the internet, on purpose. The owner runs them on the server:
```bash
python manage_keys.py list
python manage_keys.py revoke <key_id>
```
Keeping this off the network means that even if the admin token leaked, nobody could switch off every client's access.
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
| id, extraction_id | The document's own ID, and the extraction it belongs to. |
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
Use [one job](/documentation/results-endpoint), [one batch](/documentation/results-endpoint), or [up to 50 IDs](/documentation/results-endpoint). Use [recent jobs](/documentation/results-endpoint) for a short history. Save job IDs in your own database for complete tracking.
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
