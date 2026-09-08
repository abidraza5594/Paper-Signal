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
curl --fail-with-body https://papersignal.duckdns.org/api/v1/extractions \\
  -H "X-API-Key: $PAPERSIGNAL_API_KEY" \\
  -F 'files=@invoice.pdf;type=application/pdf' \\
  -F 'output_template=<invoice.schema.json' \\
  -F 'ocr_mode=auto' '''.rstrip()
node_upload = '''// Node.js 22+; run on your backend.
import { readFile } from 'node:fs/promises';

const form = new FormData();
form.append('files', new Blob([await readFile('invoice.pdf')],
  { type: 'application/pdf' }), 'invoice.pdf');
form.append('output_template', JSON.stringify({
  type: 'object', properties: { totalAmount: { type: 'number' } }
}));

const response = await fetch('https://papersignal.duckdns.org/api/v1/extractions', {
  method: 'POST',
  headers: { 'X-API-Key': process.env.PAPERSIGNAL_API_KEY },
  body: form,
  signal: AbortSignal.timeout(120_000)
});
if (!response.ok) throw new Error(`Upload HTTP ${response.status}`);
const batch = await response.json();
console.log(batch.extraction_id); // Persist this ID, then poll for the result. '''.rstrip()
python_upload = '''# Python with requests installed; run on your backend.
import json, os, requests

schema = {
    "type": "object",
    "properties": {"totalAmount": {"type": "number"}}
}
with open("invoice.pdf", "rb") as pdf:
    response = requests.post(
        "https://papersignal.duckdns.org/api/v1/extractions",
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
[Follow the quick start](/documentation/quickstart) to submit your first document. [Explore the API reference](/documentation/submit) for exact fields and responses, or [download a complete client](/documentation/examples) for bounded polling and error handling.

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

The response is HTTP 202 with an extraction_id and one queued entry per document. Save the extraction_id immediately. Do not repeat an upload just because the response was lost: duplicates can consume quota.

## 4 Get the results
Replace EXTRACTION_ID with the returned extraction_id. Poll around every two to three seconds, within your key's rate budget.
```bash
curl --fail-with-body "https://papersignal.duckdns.org/api/v1/extractions/EXTRACTION_ID" \\
  -H "X-API-Key: $PAPERSIGNAL_API_KEY"
```
The response is a list with one entry per document. Continue while any entry is queued or processing. For completed, read result.data. For failed, inspect failure_code and failure_stage. Both outcomes can show progress 100. Use a deadline; a client timeout does not cancel the work.

## 5 Use the result
```json
{"invoiceNumber":"INV-123","invoiceDate":null,"totalAmount":1250,"currency":"INR"}
```
This is an illustrative result.data object, not a live extraction. Validate dates, amounts and business rules before saving or acting on values. Retain the extraction_id for support.

## Continue your integration
[Download full clients](/documentation/examples) for upload and bounded polling. Use [batch submissions](/documentation/submit) for multiple PDFs. Once the result is saved, follow your retention policy to [delete the document](/documentation/delete).
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

endpoint('health','Check the service is up','GET','/api/health','200 OK','See whether the service is running and read its current file, page and batch limits.', '## Response and limits\n' + SECTIONS[5], auth='Public endpoint; no key required')

endpoint('submit','Send PDFs for extraction','POST','/api/v1/extractions','202 Accepted','Upload one or more PDFs with the JSON Schema of the fields you want. Returns an extraction ID to poll.', '''
## What this does
You send PDF files and a JSON Schema describing the fields you want back. The service accepts the work and returns straight away with an `extraction_id`. **The result is not in this response** - use [Get the results](/documentation/results-endpoint) with that ID.

## Request body
Use `multipart/form-data`. Send the PDF bytes, not a URL or base64.

| Field | Required | Description |
|---|---|---|
| files | Yes | One PDF file part per document. Repeat the field name for each file; do not use files[] |
| output_template | Yes | Your JSON Schema, as text, 2-12,000 characters |
| ocr_mode | No | auto (default), always or never |

## Response
HTTP 202 means the work was accepted, not finished. Every document starts as `queued`.
```json
{"extraction_id":"example-extraction-id","accepted_count":1,"rejected_count":1,
 "jobs":[{"id":"example-document-id","extraction_id":"example-extraction-id",
          "status":"queued","result":null}],
 "rejected":[{"file_name":"broken.pdf","error":"The uploaded file is not a valid PDF."}]}
```

## One bad file does not lose the good ones
Always check `accepted_count`, `rejected_count` and `rejected`. A corrupt, encrypted or over-long PDF is listed in `rejected` while the other files are accepted and processed. Rejected files do not count against your monthly quota.

If `accepted_count` is 0 there is nothing to poll, and the extraction ID returns 404.

## Limits
More files than the configured limit returns 422. Combined size over the limit returns 413. An invalid JSON Schema returns 422. Quota exhaustion returns 402 and nothing is processed.

## Before retrying
There is no idempotency key. After a timeout or a lost response the work may already have been accepted. Check before sending the same PDFs again, or the documents are counted twice.
''', code=curl_upload)
PAGES[-1]['samples'] = samples

endpoint('results-endpoint','Get the results','GET','/api/v1/extractions/{extraction_id}','200 OK','Poll the extraction ID until every document reports completed or failed, then read the extracted JSON.', '''
## What this does
Returns one entry per document you submitted. Call it every 2 seconds until every entry reports `completed` or `failed`.

| Parameter | Required | Description |
|---|---|---|
| extraction_id | Yes | The ID returned when you submitted the documents |

## Reading the response
```json
[{"id":"example-document-id","extraction_id":"example-extraction-id",
  "file_name":"invoice.pdf","status":"completed","progress":100,
  "result":{"data":{"totalAmount":4500},"evidence":[],"warnings":[]}}]
```

`result.data` matches your schema exactly: the same keys, the same nesting, missing values as `null`, and anything outside the schema removed. `result.evidence` shows which page each value came from.

## Status values
| Status | Meaning |
|---|---|
| queued | Waiting for a free worker |
| processing | Being read and extracted; progress and stage update as it goes |
| completed | Done. Read result.data |
| failed | Did not finish. Read error and failure_code |

## How long to wait
A typical document takes 15-30 seconds. Two documents are processed at a time; the rest wait their turn. Poll every 2 seconds and stop after a deadline that suits you. Stopping does not cancel the work, and you can check the same ID later.

## If a document failed
The HTTP call still succeeds. Check each entry's `failure_code` to decide what to do; see [When something goes wrong](/documentation/errors).

## Only your own documents
An extraction ID created by a different API key returns 404, not 403. The service does not reveal that it exists.
''')

endpoint('delete','Delete documents and results','DELETE','/api/v1/extractions/{extraction_id}','204 No Content','Remove the uploaded PDFs and their results once your application has stored what it needs.', '''
## What this does
Deletes every document in the extraction: the stored PDF, the job record and the result. This cannot be undone.

| Parameter | Required | Description |
|---|---|---|
| extraction_id | Yes | The ID returned when you submitted the documents |

## Responses
| Code | Meaning |
|---|---|
| 204 | Deleted. The response body is empty |
| 409 | At least one document is still processing. Wait for it to finish |
| 404 | Unknown ID, or it belongs to another key |

## Why this matters
Uploaded PDFs stay on the server until something deletes them. If your documents are sensitive, call this once you have stored the result. There is no automatic retention policy.
''')

endpoint('account','See your usage and limits','GET','/api/v1/account','200 OK','Check your key rate limit, monthly document quota and how much is left this month.', '## Usage response\n' + SECTIONS[9])

endpoint('create-key','Create an API key','POST','/api/v1/keys','201 Created','Issue a key for one client application. For the service operator only.', '''
## Who can call this
Only the service operator, using the `X-Admin-Token` header. That is a different secret from a client API key, and client keys cannot call this endpoint.

## Request body
```json
{"name":"Acme Corp","rate_limit_per_minute":60,"monthly_document_quota":200}
```
`rate_limit_per_minute` and `monthly_document_quota` are optional and fall back to the service defaults.

## Response
```json
{"key":"ps_live_xxxxxxxxxxxxxxxxxxxx",
 "api_key":{"id":"example-key-id","name":"Acme Corp",
            "key_prefix":"ps_live_xxxxxx...","rate_limit_per_minute":60,
            "monthly_document_quota":200,"documents_this_month":0}}
```

**`key` is shown once and cannot be recovered.** Only a hash and a short display prefix are stored, so a stolen database cannot be used to call the API. If a key is lost, issue a new one.

## Listing and revoking keys
These are deliberately not on the network. Run them on the server instead:
```bash
python manage_keys.py list
python manage_keys.py revoke <key_id>
```
Keeping revocation off the network means a leaked admin token cannot disable every client's access.

## Give each client its own key
One key per application. Each key sees only its own documents, carries its own rate limit and quota, and can be revoked without affecting anyone else.
''', auth='Service operator only - X-Admin-Token', group='Administration')

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
         'What was tested on the live service, and what the results were.', test_text)
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
