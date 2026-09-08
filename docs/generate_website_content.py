"""Compile reviewed documentation into typed Angular content; no runtime Markdown dependency.

Run from any directory with Python 3.11+. Only local reviewed text is compiled.
"""
from pathlib import Path
import html
import json
import re
import shutil

ROOT = Path(__file__).resolve().parents[1]
GUIDE = (ROOT / 'docs/API_INTEGRATION.md').read_text(encoding='utf-8')
SECTIONS = {int(number): body for number, body in re.findall(r'^## (\d+)\. [^\n]+\n(.*?)(?=^## \d+\.|\Z)', GUIDE, re.M | re.S)}

def inline(text):
    text = html.escape(text)
    links = {
        '../examples/integration/README.md': '/documentation/examples',
        '../examples/integration/python_client.py': '/documentation-assets/python_client.py',
        '../examples/integration/node_client.mjs': '/documentation-assets/node_client.mjs',
        '../examples/integration/invoice.schema.json': '/documentation-assets/invoice.schema.json',
        'SERVICE_ASSESSMENT.md': '/documentation/operations',
    }
    text = re.sub(r'\[([^]]+)\]\(([^)]+)\)', lambda m: f'<a href="{links.get(m[2], m[2])}">{m[1]}</a>', text)
    text = re.sub(r'`([^`]+)`', r'<code>\1</code>', text)
    text = re.sub(r'\*\*([^*]+)\*\*', r'<strong>\1</strong>', text)
    return text

def blocks(markdown):
    result, lines, i = [], markdown.strip().splitlines(), 0
    while i < len(lines):
        line = lines[i].strip()
        if not line:
            i += 1
            continue
        if line.startswith('```'):
            language = line[3:]
            code = []
            i += 1
            while i < len(lines) and not lines[i].startswith('```'):
                code.append(lines[i]); i += 1
            result.append({'kind': 'code', 'language': language, 'text': '\n'.join(code)})
        elif line.startswith('#'):
            title = re.sub(r'^#+\s*', '', line)
            result.append({'kind': 'heading', 'text': title, 'id': re.sub(r'[^a-z0-9]+', '-', title.lower()).strip('-')})
        elif line.startswith('|'):
            table = []
            while i < len(lines) and lines[i].strip().startswith('|'):
                cells = [inline(c.strip()) for c in lines[i].strip().strip('|').split('|')]
                if not all(re.fullmatch(r'[:\- ]+', c) for c in cells):
                    table.append(cells)
                i += 1
            result.append({'kind': 'table', 'headers': table[0], 'rows': table[1:]})
            continue
        elif line.startswith('- ') or re.match(r'^\d+\. ', line):
            items = []
            while i < len(lines) and (lines[i].startswith('- ') or re.match(r'^\d+\. ', lines[i])):
                items.append(inline(re.sub(r'^(?:- |\d+\. )', '', lines[i]))); i += 1
            result.append({'kind': 'list', 'items': items})
            continue
        else:
            paragraph = [line]
            while i + 1 < len(lines) and lines[i + 1].strip() and not lines[i + 1].startswith(('#', '|', '```', '- ')):
                i += 1; paragraph.append(lines[i].strip())
            result.append({'kind': 'paragraph', 'html': inline(' '.join(paragraph))})
        i += 1
    return result

PAGES = []
def page(id, title, group, summary, markdown, **extra):
    PAGES.append(dict(id=id, title=title, group=group, summary=summary, blocks=blocks(markdown), search=markdown, **extra))

SCHEMA = json.loads((ROOT / 'examples/integration/invoice.schema.json').read_text())
schema_str = json.dumps(SCHEMA, indent=2)
small_schema = '{"type":"object","properties":{"totalAmount":{"type":"number"}}}'
curl_upload = '''# Set PAPERSIGNAL_API_KEY privately in your environment.
curl --fail-with-body https://papersignal.duckdns.org/api/jobs \\
  -H "X-API-Key: $PAPERSIGNAL_API_KEY" \\
  -F 'file=@invoice.pdf;type=application/pdf' \\
  -F 'output_template=<invoice.schema.json' \\
  -F 'ocr_mode=auto' '''.rstrip()
node_upload = '''// Node.js 22+; run on your backend.
import { readFile } from 'node:fs/promises';

const form = new FormData();
form.append('file', new Blob([await readFile('invoice.pdf')],
  { type: 'application/pdf' }), 'invoice.pdf');
form.append('output_template', JSON.stringify({
  type: 'object', properties: { totalAmount: { type: 'number' } }
}));

const response = await fetch('https://papersignal.duckdns.org/api/jobs', {
  method: 'POST',
  headers: { 'X-API-Key': process.env.PAPERSIGNAL_API_KEY },
  body: form,
  signal: AbortSignal.timeout(120_000)
});
if (!response.ok) throw new Error(`Upload HTTP ${response.status}`);
const job = await response.json();
console.log(job.id); // Persist this ID, then poll for the result. '''.rstrip()
python_upload = '''# Python with requests installed; run on your backend.
import json, os, requests

schema = {
    "type": "object",
    "properties": {"totalAmount": {"type": "number"}}
}
with open("invoice.pdf", "rb") as pdf:
    response = requests.post(
        "https://papersignal.duckdns.org/api/jobs",
        headers={"X-API-Key": os.environ["PAPERSIGNAL_API_KEY"]},
        files={"file": ("invoice.pdf", pdf, "application/pdf")},
        data={"output_template": json.dumps(schema), "ocr_mode": "auto"},
        timeout=(10, 120),
    )
response.raise_for_status()
job = response.json()
print(job["id"])  # Persist this ID, then poll for the result. '''.rstrip()
samples = [{'language': label, 'code': value} for label, value in [('cURL', curl_upload), ('Node.js', node_upload), ('Python', python_upload)]]

page('overview', 'Build with PaperSignal', 'Getting started',
     'Turn PDFs into structured JSON inside your own application. Send a document, define the fields you need, and retrieve the result through a simple HTTPS API.', '''
## A service for your application
Use your own frontend and backend. PaperSignal handles PDF reading and structured extraction; your application controls user access, validates the returned values and saves them to its database. The PaperSignal web console is optional.

## Before you start
- Ask the service operator for a dedicated API key for your application and environment.
- Store the key on your backend. Never embed a shared key in browser or mobile code.
- Prepare a PDF and a JSON Schema describing the fields you need.
- Build a background polling step; extraction is asynchronous.

## Choose your starting point
[Follow the quick start](/documentation/quickstart) to submit your first document. [Explore the API reference](/documentation/upload) for exact fields and responses, or [download a complete client](/documentation/examples) for bounded polling and error handling.

## What the service supports
| Capability | Behavior |
|---|---|
| Digital and scanned PDFs | Embedded text, vision and OCR reading policies |
| Custom output fields | JSON Schema with nested objects and arrays |
| Multiple documents | Batch uploads with per-file acceptance and results |
| Client access control | Separate keys, job ownership, quotas and request limits |
| Extraction audit | Evidence, warnings, page counts and failure diagnostics |

## Integration boundaries
The current deployment uses a single-instance architecture. There are no webhooks, idempotency keys or automatic restart recovery. All extraction modes use Mistral. Read [operational considerations](/documentation/operations) before adopting it for a production workflow.
''')
page('quickstart', 'Your first extraction', 'Getting started',
     'Submit one PDF, save its job ID, and retrieve your extracted fields. The examples below run from your server or development machine.', '''
## 1 Get your API key
Ask the operator to issue a dedicated client key. Set PAPERSIGNAL_API_KEY privately in your environment. Health and documentation are public; extraction requests require your key.

## 2 Define the output
Save this as invoice.schema.json beside your PDF. A schema declares fields and types; an example invoice object is not a schema.
```json
''' + schema_str + '''
```
## 3 Submit your document
Use the request example above with your PDF. cURL examples use Bash syntax. The Python tab uses requests; downloadable Python and Node clients need no third-party packages. Let your library generate the multipart boundary.

The response is HTTP 202 with a queued job. Save its id immediately. Do not repeat an upload just because the response was lost: duplicates can consume quota.

## 4 Check the job
Replace JOB_ID with the returned id. Poll around every three seconds for one stream, within your key's shared rate budget.
```bash
curl --fail-with-body "https://papersignal.duckdns.org/api/jobs/JOB_ID" \\
  -H "X-API-Key: $PAPERSIGNAL_API_KEY"
```
Continue while status is queued or processing. For completed, read result.data. For failed, inspect failure_code and failure_stage. Both outcomes can show progress 100. Use a deadline; client timeout does not cancel the job.

## 5 Use the result
```json
{"invoiceNumber":"INV-123","invoiceDate":null,"totalAmount":1250,"currency":"INR"}
```
This is an illustrative result.data object, not a live extraction. Validate dates, amounts and business rules before saving or acting on values. Retain the job ID for support.

## Continue your integration
[Download full clients](/documentation/examples) for upload and bounded polling. Use [batch submissions](/documentation/batch-upload) for multiple PDFs. Once the result is saved, follow your retention policy to [delete the document](/documentation/delete-job).
''', samples=samples)
page('authentication', 'Authentication', 'Getting started', 'Authenticate requests with a dedicated API key and keep each application’s documents scoped to its key.', '## Client headers\n' + SECTIONS[3])

job = dict(id='example-job-id', batch_id=None, file_name='invoice.pdf', file_size=24576,
           instruction='Extract only the fields defined by the supplied JSON Schema.',
           ocr_mode='auto', status='queued', progress=0, stage='Queued', error=None, result=None,
           page_count=1, ocr_pages=0, python_text_pages=0, vision_attempted_pages=0, vision_pages=0,
           vision_failed_pages=0, text_model='mistral-small-2603', vision_model='mistral-small-2603',
           ocr_model='mistral-ocr-4-0', schema_mode='json_schema', output_template=small_schema,
           duration_ms=None, failure_code=None, failure_stage=None,
           created_at='2026-09-08T08:00:00+00:00', updated_at='2026-09-08T08:00:00+00:00')

def endpoint(id, title, method, path, success, summary, content, auth='Client API key required', code=None, group='Extraction API'):
    if code is None:
        header = 'X-Admin-Token: $PAPERSIGNAL_ADMIN_TOKEN' if group == 'Administration' else 'X-API-Key: $PAPERSIGNAL_API_KEY'
        code = f'curl --fail-with-body' + (f' -X {method}' if method not in ('GET', 'POST') else '') + f' "https://papersignal.duckdns.org{path}"'
        if auth != 'Public endpoint; no key required': code += f' \\\n  -H "{header}"'
    page(id, title, group, summary, content, method=method, path=path, success=success, auth=auth, samples=[{'language':'cURL','code':code}])

endpoint('health','Service health','GET','/api/health','200 OK','Check configured upload limits and whether the service requires authentication.', '## Response and limits\n' + SECTIONS[5], auth='Public endpoint; no key required')
endpoint('upload','Submit a PDF','POST','/api/jobs','202 Accepted','Upload a single PDF and a JSON Schema. The response contains a job ID for tracking the extraction.', '''
## Request body
Content-Type: multipart/form-data. Send PDF bytes, not a file URL or base64 JSON.
| Field | Required | Description |
|---|---|---|
| file | Yes | One PDF file part, application/pdf |
| output_template | Yes | JSON Schema as text, 2-12,000 characters |
| ocr_mode | No | auto (default), always or never |

## Accepted response
HTTP 202 returns a full job, with result null and batch_id null. This example uses a schema containing only totalAmount; output_template echoes the schema actually submitted.
```json
''' + json.dumps(job, indent=2) + '''
```
## Next step
Save id against your business record, then [poll the job](/documentation/get-job). The result does not arrive in this upload response. See [output schemas](/documentation/schema) for supported types and [OCR modes](/documentation/schema#json-schema-and-ocr-policy) for reading behavior.

## Errors
400 indicates an invalid, empty, protected, corrupt, oversized or over-page-limit PDF. 422 indicates invalid/missing form fields or schema. 401 is invalid authentication; 402 is document quota exhaustion; 429 is request-rate or queue saturation; 503 indicates AI credentials are not configured.

## Retry behavior
There is no idempotency key. After a timeout, lost response or 5xx, work may already have been accepted. Reconcile before sending the same PDF again.
''', code=curl_upload)
PAGES[-1]['samples'] = samples
endpoint('batch-upload','Submit a batch','POST','/api/jobs/batch','202 Accepted','Submit multiple PDFs with one schema and receive a separate job for each accepted file.', '''
## Request body
Use multipart/form-data. Repeat files for every PDF; do not use files[].
| Field | Required | Description |
|---|---|---|
| files | Yes | Repeated PDF file parts, up to the configured file limit |
| output_template | Yes | One JSON Schema text field, 2-12,000 characters |
| ocr_mode | No | auto, always or never; default auto |

## Partial acceptance
Always inspect accepted_count, rejected_count and rejected. The example below abbreviates each job; accepted jobs use the same full response model as single submissions.
```json
{"batch_id":"example-batch-id","accepted_count":1,"rejected_count":1,
 "jobs":[{"id":"example-job-id","status":"queued","result":null}],
 "rejected":[{"file_name":"broken.pdf","error":"The uploaded file is not a valid PDF."}]}
```
A 202 can contain zero accepted jobs. Do not poll that batch: no stored jobs means batch lookup returns 404. Queue-full rejections appear per file. One invalid file can be rejected while other files are accepted.

## Batch constraints
File-count and schema errors reject the request with 422. Excess combined size returns 413. Quota precheck includes all submitted files, even files that later fail validation. Accepted documents consume quota at submission; invalid/rejected files do not increment document usage.

## Retrieve results
Save the batch_id and every accepted job ID. [Poll the batch](/documentation/get-batch) or [poll selected IDs](/documentation/get-many). A batch does not merge documents into one business record.

Unexpected server errors can occur after some jobs have been enqueued. The batch is not transactional; do not automatically repeat the whole upload after a lost or failed response.
''', code=curl_upload.replace('/api/jobs ', '/api/jobs/batch ').replace("-F 'file=@invoice.pdf;type=application/pdf'", "-F 'files=@invoice-a.pdf;type=application/pdf' \\\n  -F 'files=@invoice-b.pdf;type=application/pdf'"))
endpoint('get-job','Retrieve a job','GET','/api/jobs/{job_id}','200 OK','Poll one job and retrieve its extraction result with the same key that submitted it.', '''
## Path parameter
| Parameter | Required | Description |
|---|---|---|
| job_id | Yes | The id returned by submission; replace {job_id} in the URL |

## Response
Returns one [job object](/documentation/results), including result when completed. Before completion result is null. Polling a failed job still returns 200; inspect status and failure_code.
```json
{"id":"example-job-id","status":"completed","progress":100,
 "result":{"data":{"totalAmount":1250},"evidence":[],"warnings":[]}}
```
This abbreviated example omits other job fields and result metadata. See [the full result contract](/documentation/results).

## Polling policy
Start around every three seconds for one stream and adjust to the key's shared request budget. Handle 429 Retry-After with backoff. Stop at completed or failed, or at your application deadline. Keep the ID for later lookup when the deadline expires.

## Errors
404 means missing or inaccessible to this key. 401 means invalid authentication. A 429 may be caused by uploads, reads or polls from other callers using the same key.
''')
endpoint('get-batch','Retrieve a batch','GET','/api/batches/{batch_id}','200 OK','Retrieve all jobs visible to your key within a submitted batch.', '''
## Path parameter
| Parameter | Required | Description |
|---|---|---|
| batch_id | Yes | Batch ID returned by POST /api/jobs/batch |

## Response
An array of full job objects, ordered by creation time then ID. There is no batch wrapper, aggregate status or pagination. Match jobs by ID rather than array position.
```json
[
  {"id":"example-job-a","status":"completed","result":{"data":{"totalAmount":1250}}},
  {"id":"example-job-b","status":"processing","result":null}
]
```
The example is abbreviated. Keep polling while any expected job is queued or processing. Completed and failed are terminal. One failed job does not imply all other jobs failed.

## Missing batches
404 means no visible jobs remain, including an unknown batch, another key's batch, a submission with zero accepted files or a batch whose jobs were deleted. Persist accepted IDs and handle missing jobs explicitly.
''')
endpoint('get-many','Retrieve selected jobs','GET','/api/jobs/batch?ids=id1,id2','200 OK','Check up to 50 supplied job IDs with one request to reduce polling traffic.', '''
## Query parameter
| Parameter | Required | Description |
|---|---|---|
| ids | Yes | Comma-separated nonempty job IDs; maximum 50 supplied nonempty IDs |

## Response behavior
Returns an array of full job objects. Duplicates are removed; input order is retained. Unknown or inaccessible jobs are silently omitted. If none are visible, the response is an empty array with HTTP 200.
```json
[]
```
Compare returned IDs against your expected IDs; an omitted job is not proof that processing completed. An empty/too-long list or missing ids returns 422.
''')
endpoint('list-jobs','List recent jobs','GET','/api/jobs?limit=20','200 OK','List the latest jobs belonging to your client key.', '''
## Query parameter
| Parameter | Required | Description |
|---|---|---|
| limit | No | Integer, defaults to 20; clamped to 1-100 |

## Response
An array of full job objects, newest first. If the key has no jobs, returns []. There is no offset, cursor, total count or full-history export endpoint. Maintain your application's own job-ID index for complete history.

## Reconcile an uncertain upload
Recent jobs may help investigate a lost upload response. Filename is not unique; use your application's record of submission time and operator support before retrying. Do not infer exactly-once behavior from this list.
''')
endpoint('delete-job','Delete a job','DELETE','/api/jobs/{job_id}','204 No Content','Remove a stored PDF and its job/result record after your application has saved the result.', '## Deletion behavior\n' + SECTIONS[10])
endpoint('usage','Usage and quotas','GET','/api/usage','200 OK','Read the client key’s current monthly document usage and shared request limit.', '## Usage response\n' + SECTIONS[9])

endpoint('create-key','Create an API key','POST','/api/admin/keys','201 Created','Issue a dedicated credential for a consuming application. This operation is for the service operator.', '''
## Request body
Content-Type: application/json. Use your private X-Admin-Token header.
| Field | Required | Description |
|---|---|---|
| name | Yes | 1-120 characters; whitespace-only names rejected |
| rate_limit_per_minute | No | Integer 1-10,000; omitted/null uses server default |
| monthly_document_quota | No | Integer 1-10,000,000; omitted/null uses server default |
```json
{"name":"CRM production","rate_limit_per_minute":60,"monthly_document_quota":1000}
```
## One-time credential
201 returns a raw key and metadata. Store the raw key securely now; list operations never return it.
```json
{"key":"<NEW_RAW_KEY>","api_key":{"id":"example-key-id","name":"CRM production",
 "key_prefix":"ps_live_ABC123...","rate_limit_per_minute":60,
 "monthly_document_quota":1000,"documents_this_month":0,
 "created_at":"2026-09-08T08:00:00+00:00","last_used_at":null,"revoked_at":null}}
```
The service stores only a SHA-256 hash plus a display prefix. Give consumers the client key, never the admin token or Mistral credential.

## Errors and ownership
401 means missing/incorrect admin token; 503 means admin HTTP management is unconfigured; 422 means invalid payload. A new key has a different owner and cannot access previous-key jobs. There is no quota-update or ownership-transfer endpoint.
''', auth='Service operator only · X-Admin-Token', group='Administration', code='''curl --fail-with-body https://papersignal.duckdns.org/api/admin/keys \\
  -H "X-Admin-Token: $PAPERSIGNAL_ADMIN_TOKEN" \\
  -H 'Content-Type: application/json' \\
  -d '{"name":"CRM production","rate_limit_per_minute":60,"monthly_document_quota":1000}' ''')
endpoint('list-keys','List API keys','GET','/api/admin/keys','200 OK','Inspect client-key metadata, including revoked keys and current-month document usage.', '''
## Response
Returns an array of key metadata, newest first. Each item has id, name, key_prefix, rate_limit_per_minute, monthly_document_quota, documents_this_month, created_at, last_used_at and revoked_at. There is no pagination and raw key values are never returned.
```json
[]
```
An empty array indicates no issued keys. Use the metadata ID for revocation, not the display prefix. For consumer self-service usage, use [GET /api/usage](/documentation/usage).

## Errors
401: missing/incorrect admin token. 503: ADMIN_TOKEN is not configured on the service.
''', auth='Service operator only · X-Admin-Token', group='Administration')
endpoint('revoke-key','Revoke an API key','DELETE','/api/admin/keys/{key_id}','204 No Content','Disable a client key so subsequent requests are rejected.', '''
## Path parameter
| Parameter | Required | Description |
|---|---|---|
| key_id | Yes | Metadata ID from key creation or key listing; not the raw credential |

## Response and effect
204 with an empty body means revocation succeeded. Subsequent requests using the key return 401. Accepted jobs are not cancelled, local PDFs/results are not deleted, and ownership is not transferred.

## Errors
404: unknown key ID. 409: key already revoked. 401: wrong/missing admin token. 503: admin management is not configured.

## Rotation planning
A replacement key cannot read jobs created by the previous key. Retrieve needed results before revocation or implement an operator-controlled ownership migration. No un-revoke or rotation endpoint exists.
''', auth='Service operator only · X-Admin-Token', group='Administration')

page('schema','Schemas and OCR','Integration guides','Define exactly which fields you need, understand null values, and choose the page-reading policy.', '## JSON Schema and OCR policy\n' + SECTIONS[7])
page('results','Jobs and results','Integration guides','Understand the job lifecycle, output fields, evidence and processing diagnostics.', '## Reading jobs\n' + SECTIONS[8])
page('errors','Errors and retries','Integration guides','Handle HTTP errors and failed jobs separately, and avoid duplicate work when an upload response is uncertain.', '## Response errors\n' + SECTIONS[12])
page('cors','Browser integration','Integration guides','Keep shared keys on your backend. Configure CORS only for an intentional direct browser integration.', '## CORS configuration\n' + SECTIONS[13])
example_readme = (ROOT / 'examples/integration/README.md').read_text()
page('examples','Complete client examples','Integration guides','Download or copy runnable upload-and-poll clients with timeouts and error handling.', '''
## Download clients
[Python client](/documentation-assets/python_client.py) uses Python 3.11+ and the standard library only. [Node.js client](/documentation-assets/node_client.mjs) uses Node.js 22+ and native Fetch/FormData. Both use the [invoice schema](/documentation-assets/invoice.schema.json) by default.

These clients upload once and poll until completed/failed or a ten-minute deadline. They print the accepted job ID immediately; persist it in your actual application. Result output includes data, evidence, warnings and document metadata.

## Configure your environment
The operator must issue your application's key. Set it privately; never commit it. These PowerShell commands use placeholders, not real credentials.
```powershell
$env:PAPERSIGNAL_API_KEY = '<YOUR_CLIENT_KEY>'
$env:PAPERSIGNAL_BASE_URL = 'https://papersignal.duckdns.org'
```
## Run the examples
Save the client and invoice.schema.json in the same folder, then run:
```powershell
python python_client.py 'C:\\Documents\\invoice.pdf'
node node_client.mjs 'C:\\Documents\\invoice.pdf'
```
Running a client against AWS uploads the PDF, consumes quota and may incur provider usage. Use a small synthetic document for initial checks. Clients buffer files in memory; use streaming multipart for large files.

## Application integration
Move uploads and polling into a backend/background worker. Coordinate polling across callers and handle partial batches separately. There is no automatic upload retry or automatic deletion. A polling deadline does not cancel work; retain the job ID and check later.

## Validation boundary
Local client checks cover controlled success, rate-limit retry, terminal job failure and authentication errors. They are not live Mistral extraction tests. Before onboarding, verify your dedicated key with synthetic text and scanned PDFs.
''', samples=[{'language':'Python','code':(ROOT / 'examples/integration/python_client.py').read_text()}, {'language':'Node.js','code':(ROOT / 'examples/integration/node_client.mjs').read_text()}])
assessment = (ROOT / 'docs/SERVICE_ASSESSMENT.md').read_text()
operations = assessment.split('## Production limitations and decisions')[1].split('## Handoff and sources')[0]
page('operations','Operational considerations','Integration guides','Plan service limits, data handling and recovery before connecting a production workflow.', '## Production readiness\n' + operations + '\n## Data handling\n' + assessment.split('## Access and data handling')[1].split('## Production limitations')[0] + '\n## Verified on 8 September 2026\n' + assessment.split('## Verification evidence')[1].split('## Integration design')[0])

from website_plain_english import apply_plain_english
apply_plain_english(PAGES, blocks, schema_str, json.dumps(job, indent=2))

test_report = ROOT / 'docs/API_TEST_RESULTS.md'
if test_report.exists():
    test_text = test_report.read_text(encoding='utf-8')
    test_text = re.sub(r'^# [^\n]+\n', '', test_text)
    page('test-results', 'API test results', 'Getting started',
         'See what was tested, what worked, and what still needs attention.', test_text)
    report_page = PAGES.pop()
    PAGES.insert(2, report_page)

types = '''// Generated by docs/generate_website_content.py from reviewed local documentation.
export interface DocBlock { kind: 'heading' | 'paragraph' | 'list' | 'table' | 'code'; id?: string; text?: string; html?: string; language?: string; items?: string[]; headers?: string[]; rows?: string[][]; }
export interface DocPage { id: string; title: string; group: string; summary: string; search: string; blocks: DocBlock[]; method?: string; path?: string; success?: string; auth?: string; samples?: { language: string; code: string }[]; }
export const DOC_PAGES: DocPage[] = '''
(ROOT / 'frontend/src/app/documentation/documentation-content.ts').write_text(types + json.dumps(PAGES, indent=2, ensure_ascii=False) + ';\n', encoding='utf-8')
assets = ROOT / 'frontend/public/documentation-assets'
assets.mkdir(parents=True, exist_ok=True)
for name in ('invoice.schema.json','python_client.py','node_client.mjs'):
    shutil.copyfile(ROOT / 'examples/integration' / name, assets / name)
print(f'Compiled {len(PAGES)} documentation pages and 3 downloadable examples.')
