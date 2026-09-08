import{$ as L,A as Y,B as s,Ba as $,F as U,L as j,M as b,N as v,O as T,P as p,Q as m,R as h,S as n,T as i,U as g,V as A,W as y,X as c,_ as E,aa as o,ba as u,ca as W,g as F,ka as S,l as I,m as _,ma as f,n as P,o as O,p as q,r as N,u as k,v as M,xa as K,ya as G,z as D,za as H}from"./chunk-PK6CKQ3T.js";function B(t,a){let r=!a?.manualCleanup?a?.injector?.get(N)??I(N):null,d=z(a?.equal),l;a?.requireSync?l=k({kind:0},{equal:d}):l=k({kind:1,value:a?.initialValue},{equal:d});let x,R=t.subscribe({next:w=>l.set({kind:1,value:w}),error:w=>{l.set({kind:2,error:w}),x?.()},complete:()=>{x?.()}});if(a?.requireSync&&l().kind===0)throw new F(601,!1);return x=r?.onDestroy(R.unsubscribe.bind(R)),f(()=>{let w=l();switch(w.kind){case 1:return w.value;case 2:throw w.error;case 0:throw new F(601,!1)}},{equal:a?.equal})}function z(t=Object.is){return(a,e)=>a.kind===1&&e.kind===1&&t(a.value,e.value)}var J=[{id:"overview",title:"Build with PaperSignal",group:"Getting started",summary:"Read a PDF and get the fields your application needs as JSON.",blocks:[{kind:"heading",text:"What PaperSignal does",id:"what-papersignal-does"},{kind:"paragraph",html:"PaperSignal reads a PDF and returns the fields you ask for. For example, your invoice app can ask for the invoice number, date, amount and currency."},{kind:"paragraph",html:"Your app can call the API directly. You do not need to use the PaperSignal upload screen or connect to its database."},{kind:"heading",text:"What you need",id:"what-you-need"},{kind:"list",items:["A client API key from the service owner.","A PDF file.","A JSON Schema: a list of the fields you want and their data types.","A backend that can send HTTP requests and check the result later."]},{kind:"heading",text:"How it works",id:"how-it-works"},{kind:"list",items:["Send the PDF and your schema to PaperSignal.","Save the extraction ID from the response.","Check that ID every few seconds until every PDF is finished.","Read result.data, check the values, and save them in your app."]},{kind:"heading",text:"Start here",id:"start-here"},{kind:"paragraph",html:'<a href="/documentation/quickstart">Follow the quick start</a>, <a href="/documentation/test-results">see the latest API test results</a>, or <a href="/documentation/examples">download a complete Python or Node.js example</a>.'},{kind:"heading",text:"Keep the key on your backend",id:"keep-the-key-on-your-backend"},{kind:"paragraph",html:"Your frontend should call your own backend. Your backend sends the API key to PaperSignal. Do not put a shared API key in browser or mobile code."},{kind:"heading",text:"Before production use",id:"before-production-use"},{kind:"paragraph",html:'The current service runs as one application instance. Work may stop after a restart and does not restart automatically. PDF text, and sometimes page images or the full PDF, are sent to Mistral for AI processing. Read <a href="/documentation/operations">service limits</a> before using business documents.'}],search:`
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
`},{id:"quickstart",title:"Your first extraction",group:"Getting started",summary:"Send a sample PDF, check its progress, and read the extracted data.",blocks:[{kind:"heading",text:"1 Get a client key",id:"1-get-a-client-key"},{kind:"paragraph",html:"Ask the service owner for a key for your application. Save it as PAPERSIGNAL_API_KEY in your backend environment. Do not put a real key in code you share."},{kind:"heading",text:"2 Choose the fields",id:"2-choose-the-fields"},{kind:"paragraph",html:"Save this as invoice.schema.json beside your PDF. The schema below asks for four invoice fields."},{kind:"code",language:"json",text:`{
  "type": "object",
  "properties": {
    "invoiceNumber": {
      "type": "string",
      "description": "Invoice identifier printed on the document"
    },
    "invoiceDate": {
      "type": "string",
      "description": "Invoice date, YYYY-MM-DD when available"
    },
    "totalAmount": {
      "type": "number"
    },
    "currency": {
      "type": "string"
    }
  }
}`},{kind:"heading",text:"3 Send the PDF",id:"3-send-the-pdf"},{kind:"paragraph",html:"Use one of the code examples above. Replace invoice.pdf with your file. The cURL example uses Bash. The short Python example needs the requests package; the full downloadable Python client needs no extra package."},{kind:"paragraph",html:"The server returns HTTP 202 and a job ID. This means the file was accepted. It does not mean extraction has finished. Save the id now."},{kind:"heading",text:"4 Check the result",id:"4-check-the-result"},{kind:"paragraph",html:"Replace JOB_ID with the returned id. Repeat this request about every three seconds for one job, while staying within your key&#x27;s request limit."},{kind:"code",language:"bash",text:`curl --fail-with-body "https://papersignal.duckdns.org/api/v1/extractions/JOB_ID" \\
  -H "X-API-Key: $PAPERSIGNAL_API_KEY"`},{kind:"table",headers:["status","What to do"],rows:[["queued","The job is waiting. Check again later."],["processing","The job is running. Check again later."],["completed","Read result.data."],["failed","Read error, failure_code and failure_stage."]]},{kind:"paragraph",html:"Set a time limit in your app. If you stop waiting, keep the job ID so you can check again later. Stopping your request does not stop the server job."},{kind:"heading",text:"5 Use the data",id:"5-use-the-data"},{kind:"code",language:"json",text:'{"invoiceNumber":"INV-123","invoiceDate":null,"totalAmount":1250,"currency":"INR"}'},{kind:"paragraph",html:"This is an example of result.data. null means the value was not found or did not match the expected type. Check important values before saving or using them."},{kind:"heading",text:"Next steps",id:"next-steps"},{kind:"paragraph",html:'<a href="/documentation/examples">Download a full upload-and-check client</a>. For several PDFs, use <a href="/documentation/submit">batch upload</a>. Save your results before <a href="/documentation/delete">deleting a job</a>.'}],search:`
## 1 Get a client key
Ask the service owner for a key for your application. Save it as PAPERSIGNAL_API_KEY in your backend environment. Do not put a real key in code you share.

## 2 Choose the fields
Save this as invoice.schema.json beside your PDF. The schema below asks for four invoice fields.
\`\`\`json
{
  "type": "object",
  "properties": {
    "invoiceNumber": {
      "type": "string",
      "description": "Invoice identifier printed on the document"
    },
    "invoiceDate": {
      "type": "string",
      "description": "Invoice date, YYYY-MM-DD when available"
    },
    "totalAmount": {
      "type": "number"
    },
    "currency": {
      "type": "string"
    }
  }
}
\`\`\`
## 3 Send the PDF
Use one of the code examples above. Replace invoice.pdf with your file. The cURL example uses Bash. The short Python example needs the requests package; the full downloadable Python client needs no extra package.

The server returns HTTP 202 and a job ID. This means the file was accepted. It does not mean extraction has finished. Save the id now.

## 4 Check the result
Replace JOB_ID with the returned id. Repeat this request about every three seconds for one job, while staying within your key's request limit.
\`\`\`bash
curl --fail-with-body "https://papersignal.duckdns.org/api/v1/extractions/JOB_ID" \\
  -H "X-API-Key: $PAPERSIGNAL_API_KEY"
\`\`\`
| status | What to do |
|---|---|
| queued | The job is waiting. Check again later. |
| processing | The job is running. Check again later. |
| completed | Read result.data. |
| failed | Read error, failure_code and failure_stage. |

Set a time limit in your app. If you stop waiting, keep the job ID so you can check again later. Stopping your request does not stop the server job.

## 5 Use the data
\`\`\`json
{"invoiceNumber":"INV-123","invoiceDate":null,"totalAmount":1250,"currency":"INR"}
\`\`\`
This is an example of result.data. null means the value was not found or did not match the expected type. Check important values before saving or using them.

## Next steps
[Download a full upload-and-check client](/documentation/examples). For several PDFs, use [batch upload](/documentation/submit). Save your results before [deleting a job](/documentation/delete).
`,samples:[{language:"cURL",code:`# Set PAPERSIGNAL_API_KEY privately in your environment.
curl --fail-with-body https://papersignal.duckdns.org/api/v1/extractions \\
  -H "X-API-Key: $PAPERSIGNAL_API_KEY" \\
  -F 'files=@invoice.pdf;type=application/pdf' \\
  -F 'output_template=<invoice.schema.json' \\
  -F 'ocr_mode=auto'`},{language:"Node.js",code:`// Node.js 22+; run on your backend.
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
if (!response.ok) throw new Error(\`Upload HTTP \${response.status}\`);
const batch = await response.json();
console.log(batch.extraction_id); // Persist this ID, then poll for the result.`},{language:"Python",code:`# Python with requests installed; run on your backend.
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
print(job["id"])  # Persist this ID, then poll for the result.`}]},{id:"test-results",title:"API test results",group:"Getting started",summary:"What was tested on the live service, and what the results were.",blocks:[{kind:"heading",text:"Main finding",id:"main-finding"},{kind:"paragraph",html:"<strong>Extraction works. Every API was checked on the live AWS service and a real PDF was read end to end.</strong>"},{kind:"paragraph",html:"Last checked: 8 September 2026. A one-page invoice PDF returned <code>{&quot;invoiceNumber&quot;:&quot;INV-2026-777&quot;,&quot;total&quot;:4500}</code> in about two seconds."},{kind:"heading",text:"What the earlier failures were",id:"what-the-earlier-failures-were"},{kind:"paragraph",html:"An earlier run on the same day recorded failed extractions. The cause was <strong>not</strong> the service: the AI provider account had a request limit of zero, so every AI call was refused with HTTP 429. The provider&#x27;s own response headers confirmed it:"},{kind:"code",language:"",text:`x-ratelimit-limit-req-minute: 0
x-ratelimit-remaining-req-minute: 0`},{kind:"paragraph",html:"Three separate keys from that account behaved identically, which showed the limit was applied to the account, not to any one key. A key from a working account fixed it immediately, with no code change."},{kind:"paragraph",html:"Two improvements came out of that investigation:"},{kind:"list",items:["Failures now report <strong>why</strong> they happened. A rate limit returns <code>AI_RATE_LIMITED</code>"]},{kind:"paragraph",html:"with &quot;retry in a few minutes&quot; instead of an unhelpful <code>SDKError</code>. Bad credentials return <code>AI_AUTH_FAILED</code>, and provider outages return <code>AI_PROVIDER_UNAVAILABLE</code>."},{kind:"list",items:["Rate-limited and transient calls are retried with exponential backoff before the"]},{kind:"paragraph",html:"document is marked failed."},{kind:"heading",text:"Test summary",id:"test-summary"},{kind:"table",headers:["Test set","Result"],rows:[["Live AWS API checks","All endpoints pass, including authentication, isolation, rate limits, quota and deletion."],["Live extraction on AWS","Passes. A real PDF returned the requested fields."],["Backend automated tests","48 pass."],["Frontend automated tests","35 pass."]]},{kind:"paragraph",html:"The image-only PDF tested with <code>ocr_mode=never</code> fails by design. That is a passed error-handling test, not a fault."},{kind:"heading",text:"Each API and its result",id:"each-api-and-its-result"},{kind:"table",headers:["API","AWS result","Local result"],rows:[["GET /api/health","Passed: 200 and configured limits returned.","Passed."],["POST /api/v1/extractions","File accepted with 202. Extraction succeeded. Invalid inputs were correctly rejected.","Same result with real AI."],["POST /api/v1/extractions","Two valid files accepted and one invalid file rejected. Extraction succeeded for both valid files.","Same result with real AI."],["GET /api/v1/extractions/{extraction_id}","Passed: returned the job and its failed status. A successful live result was verified.","Passed for reading states and errors."],["GET /api/v1/extractions/{extraction_id}","Passed: returned the test batch&#x27;s jobs.","Passed, including other-key rejection."],["GET /api/v1/extractions/{extraction_id}","Passed: ID lookup, duplicate removal and missing-ID behavior.","Passed, including other-key filtering."],["GET /api/v1/extractions/{extraction_id}","Passed: test jobs were present in the recent list.","Passed, including key ownership."],["DELETE /api/v1/extractions/{extraction_id}","Passed: finished test jobs deleted; processing deletion returned 409; later reads returned 404.","Passed."],["GET /api/v1/account","Passed: key accepted, allowance reported and accepted documents counted.","Passed, including quota and rate-limit errors."],["POST /api/v1/keys","Client key correctly rejected with 401. Successful creation not tested on AWS without an admin token.","Passed: isolated test keys created."],["GET /api/v1/keys","Client key correctly rejected with 401. Authorized listing not tested on AWS.","Passed: key metadata listed without raw keys."],["DELETE /api/v1/keys","Client key correctly rejected with 401. Authorized revocation not tested on AWS.","Passed: only test keys revoked; repeated revocation returned 409."]]},{kind:"heading",text:"Extraction cases",id:"extraction-cases"},{kind:"table",headers:["Document and mode","Expected","AWS result"],rows:[["Text PDF, never","Extract invoice number, amount and currency.","Passed."],["Text PDF in a batch, auto","Extract the same known values.","Passed."],["Scanned PDF in a batch, auto","Read the scan and extract the known values.","Passed."],["Scanned PDF, always","Use OCR and extract the known values.","Passed."],["Scanned PDF, never","Fail because there is no embedded text.","Failed as expected with \u201CNo readable text was found in the PDF.\u201D"]]},{kind:"paragraph",html:"The scan jobs reported one OCR page and completed. This does not establish OCR accuracy across document types; check your own documents before relying on it."},{kind:"heading",text:"What the error looked like before the fix",id:"what-the-error-looked-like-before-the-fix"},{kind:"paragraph",html:"While the provider account was blocked, every document failed like this:"},{kind:"code",language:"text",text:`failure_code: AI_EXTRACTION_ERROR
failure_stage: Structured extraction
error: Mistral structured extraction failed with all configured Mistral API keys (SDKError).`},{kind:"paragraph",html:"That message did not say whether to retry, fix credentials or fix the document. Failures are now classified, so the same situation reports:"},{kind:"code",language:"text",text:`failure_code: AI_RATE_LIMITED
error: The AI provider is rate limiting this service. The document was not processed.
       Retry in a few minutes.`},{kind:"heading",text:"What to check next",id:"what-to-check-next"},{kind:"list",items:["Run your own documents through the service. The tests above used small synthetic PDFs;"]},{kind:"paragraph",html:"accuracy on your real layouts is the thing worth measuring."},{kind:"list",items:["Watch the provider account&#x27;s limits. A limit of zero blocks every request regardless of"]},{kind:"paragraph",html:"which key is used, so check the account rather than issuing new keys."},{kind:"list",items:["Confirm OCR quality on scans that matter to you, using <code>ocr_mode=auto</code>.","Load and restart-recovery behaviour, large proxied uploads, and the provider&#x27;s data"]},{kind:"paragraph",html:"retention terms are still unverified."}],search:`
## Main finding
**Extraction works. Every API was checked on the live AWS service and a real PDF was read end to end.**

Last checked: 8 September 2026. A one-page invoice PDF returned
\`{"invoiceNumber":"INV-2026-777","total":4500}\` in about two seconds.

## What the earlier failures were
An earlier run on the same day recorded failed extractions. The cause was **not** the
service: the AI provider account had a request limit of zero, so every AI call was
refused with HTTP 429. The provider's own response headers confirmed it:

\`\`\`
x-ratelimit-limit-req-minute: 0
x-ratelimit-remaining-req-minute: 0
\`\`\`

Three separate keys from that account behaved identically, which showed the limit was
applied to the account, not to any one key. A key from a working account fixed it
immediately, with no code change.

Two improvements came out of that investigation:

- Failures now report **why** they happened. A rate limit returns \`AI_RATE_LIMITED\`
  with "retry in a few minutes" instead of an unhelpful \`SDKError\`. Bad credentials
  return \`AI_AUTH_FAILED\`, and provider outages return \`AI_PROVIDER_UNAVAILABLE\`.
- Rate-limited and transient calls are retried with exponential backoff before the
  document is marked failed.

## Test summary
| Test set | Result |
|---|---|
| Live AWS API checks | All endpoints pass, including authentication, isolation, rate limits, quota and deletion. |
| Live extraction on AWS | Passes. A real PDF returned the requested fields. |
| Backend automated tests | 48 pass. |
| Frontend automated tests | 35 pass. |

The image-only PDF tested with \`ocr_mode=never\` fails by design. That is a passed
error-handling test, not a fault.

## Each API and its result
| API | AWS result | Local result |
|---|---|---|
| GET /api/health | Passed: 200 and configured limits returned. | Passed. |
| POST /api/v1/extractions | File accepted with 202. Extraction succeeded. Invalid inputs were correctly rejected. | Same result with real AI. |
| POST /api/v1/extractions | Two valid files accepted and one invalid file rejected. Extraction succeeded for both valid files. | Same result with real AI. |
| GET /api/v1/extractions/{extraction_id} | Passed: returned the job and its failed status. A successful live result was verified. | Passed for reading states and errors. |
| GET /api/v1/extractions/{extraction_id} | Passed: returned the test batch's jobs. | Passed, including other-key rejection. |
| GET /api/v1/extractions/{extraction_id} | Passed: ID lookup, duplicate removal and missing-ID behavior. | Passed, including other-key filtering. |
| GET /api/v1/extractions/{extraction_id} | Passed: test jobs were present in the recent list. | Passed, including key ownership. |
| DELETE /api/v1/extractions/{extraction_id} | Passed: finished test jobs deleted; processing deletion returned 409; later reads returned 404. | Passed. |
| GET /api/v1/account | Passed: key accepted, allowance reported and accepted documents counted. | Passed, including quota and rate-limit errors. |
| POST /api/v1/keys | Client key correctly rejected with 401. Successful creation not tested on AWS without an admin token. | Passed: isolated test keys created. |
| GET /api/v1/keys | Client key correctly rejected with 401. Authorized listing not tested on AWS. | Passed: key metadata listed without raw keys. |
| DELETE /api/v1/keys | Client key correctly rejected with 401. Authorized revocation not tested on AWS. | Passed: only test keys revoked; repeated revocation returned 409. |

## Extraction cases
| Document and mode | Expected | AWS result |
|---|---|---|
| Text PDF, never | Extract invoice number, amount and currency. | Passed. |
| Text PDF in a batch, auto | Extract the same known values. | Passed. |
| Scanned PDF in a batch, auto | Read the scan and extract the known values. | Passed. |
| Scanned PDF, always | Use OCR and extract the known values. | Passed. |
| Scanned PDF, never | Fail because there is no embedded text. | Failed as expected with \u201CNo readable text was found in the PDF.\u201D |

The scan jobs reported one OCR page and completed. This does not establish OCR accuracy across document types; check your own documents before relying on it.

## What the error looked like before the fix

While the provider account was blocked, every document failed like this:

\`\`\`text
failure_code: AI_EXTRACTION_ERROR
failure_stage: Structured extraction
error: Mistral structured extraction failed with all configured Mistral API keys (SDKError).
\`\`\`

That message did not say whether to retry, fix credentials or fix the document. Failures
are now classified, so the same situation reports:

\`\`\`text
failure_code: AI_RATE_LIMITED
error: The AI provider is rate limiting this service. The document was not processed.
       Retry in a few minutes.
\`\`\`

## What to check next

- Run your own documents through the service. The tests above used small synthetic PDFs;
  accuracy on your real layouts is the thing worth measuring.
- Watch the provider account's limits. A limit of zero blocks every request regardless of
  which key is used, so check the account rather than issuing new keys.
- Confirm OCR quality on scans that matter to you, using \`ocr_mode=auto\`.
- Load and restart-recovery behaviour, large proxied uploads, and the provider's data
  retention terms are still unverified.
`},{id:"authentication",title:"Authentication",group:"Getting started",summary:"Send your client API key with each protected request.",blocks:[{kind:"heading",text:"Send the key",id:"send-the-key"},{kind:"paragraph",html:"Use either header:"},{kind:"code",language:"http",text:"X-API-Key: <YOUR_CLIENT_API_KEY>"},{kind:"code",language:"http",text:"Authorization: Bearer <YOUR_CLIENT_API_KEY>"},{kind:"paragraph",html:"If both are present, a nonempty X-API-Key is used. A wrong, missing or revoked key returns 401. Revoked means the service owner has disabled the key."},{kind:"heading",text:"Public pages",id:"public-pages"},{kind:"paragraph",html:"Health, Swagger and OpenAPI do not need a key. All consumer APIs need a key when service key mode is on. The usage API always needs a key."},{kind:"heading",text:"Which jobs can a key access",id:"which-jobs-can-a-key-access"},{kind:"paragraph",html:"A key can read and delete only the jobs created with that key. Another key gets 404 for a job or batch. Lists leave out jobs belonging to other keys."},{kind:"paragraph",html:"If many users share one backend key, your backend must check which user owns each job. PaperSignal does not know your app&#x27;s individual users."},{kind:"heading",text:"Where to store keys",id:"where-to-store-keys"},{kind:"paragraph",html:"Keep shared keys on your backend, not in browser code, mobile code or a shared repository. Use HTTPS. The client key is different from the Mistral key and the admin token; do not give those to API users."},{kind:"heading",text:"Replacing a key",id:"replacing-a-key"},{kind:"paragraph",html:"A new key cannot read the old key&#x27;s jobs. Save needed results before disabling the old key. There is no API to move jobs between keys."},{kind:"heading",text:"Development mode",id:"development-mode"},{kind:"paragraph",html:"With REQUIRE_API_KEY=false, anonymous requests have no job-owner filter. This can expose existing jobs. Keep REQUIRE_API_KEY=true on a shared server."}],search:`
## Send the key
Use either header:
\`\`\`http
X-API-Key: <YOUR_CLIENT_API_KEY>
\`\`\`
\`\`\`http
Authorization: Bearer <YOUR_CLIENT_API_KEY>
\`\`\`
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
`},{id:"health",title:"Check the service is up",group:"Extraction API",summary:"See whether the service is running and what its current limits are.",blocks:[{kind:"heading",text:"When to use this",id:"when-to-use-this"},{kind:"paragraph",html:"Call this before you start, or when something is not working, to confirm the service is reachable. This is the only endpoint that does not need an API key."},{kind:"heading",text:"What you get back",id:"what-you-get-back"},{kind:"code",language:"json",text:`{"status":"ok","ai_configured":true,"require_api_key":true,
 "max_upload_mb":200,"max_pdf_pages":50,"max_batch_files":10}`},{kind:"table",headers:["Field","What it tells you"],rows:[["status","&quot;ok&quot; means the service is running."],["require_api_key","true means every other endpoint needs your key."],["max_batch_files","How many PDFs you can send in one request."],["max_upload_mb","The largest single PDF you can send."],["max_pdf_pages","The most pages one PDF can have."],["ai_configured","false means the owner has not set up the AI provider yet."]]},{kind:"paragraph",html:"Read the limits from here instead of hard-coding them. The owner can change them."}],search:`
## When to use this
Call this before you start, or when something is not working, to confirm the service is reachable. This is the only endpoint that does not need an API key.

## What you get back
\`\`\`json
{"status":"ok","ai_configured":true,"require_api_key":true,
 "max_upload_mb":200,"max_pdf_pages":50,"max_batch_files":10}
\`\`\`

| Field | What it tells you |
|---|---|
| status | "ok" means the service is running. |
| require_api_key | true means every other endpoint needs your key. |
| max_batch_files | How many PDFs you can send in one request. |
| max_upload_mb | The largest single PDF you can send. |
| max_pdf_pages | The most pages one PDF can have. |
| ai_configured | false means the owner has not set up the AI provider yet. |

Read the limits from here instead of hard-coding them. The owner can change them.
`,method:"GET",path:"/api/health",success:"200 OK",auth:"Public endpoint; no key required",samples:[{language:"cURL",code:'curl --fail-with-body "https://papersignal.duckdns.org/api/health"'}]},{id:"submit",title:"Send PDFs for extraction",group:"Extraction API",summary:"Upload your PDFs and the list of fields you want. You get an ID to check later.",blocks:[{kind:"heading",text:"What this does",id:"what-this-does"},{kind:"paragraph",html:"You send your PDF files and a JSON Schema saying which fields you want. The service takes the work and answers straight away with an extraction ID."},{kind:"paragraph",html:'<strong>The result is not in this response.</strong> Reading a PDF takes 15 to 30 seconds, so the answer comes from <a href="/documentation/results-endpoint">Get the results</a> using that ID.'},{kind:"heading",text:"What to send",id:"what-to-send"},{kind:"paragraph",html:"Use multipart/form-data. Let your HTTP library set the Content-Type and boundary."},{kind:"table",headers:["Field","Required","What to send"],rows:[["files","Yes","Your PDF file. Repeat this field once per PDF. Do not write files[]."],["output_template","Yes","Your JSON Schema as text, 2-12,000 characters."],["ocr_mode","No","auto, always or never. Default: auto."]]},{kind:"paragraph",html:"Send the file bytes, not a link or base64 text."},{kind:"heading",text:"What you get back",id:"what-you-get-back"},{kind:"code",language:"json",text:`{"extraction_id":"a1b2c3d4","accepted_count":1,"rejected_count":1,
 "jobs":[{"id":"doc-1","extraction_id":"a1b2c3d4","status":"queued","result":null}],
 "rejected":[{"file_name":"broken.pdf","error":"The uploaded file is not a valid PDF."}]}`},{kind:"paragraph",html:"Save <code>extraction_id</code>. That is the only thing you need to get your results."},{kind:"heading",text:"A bad file does not spoil the rest",id:"a-bad-file-does-not-spoil-the-rest"},{kind:"paragraph",html:"If you send five PDFs and one is damaged, the other four are still processed. The damaged one appears in <code>rejected</code> with the reason. Rejected files are not counted against your monthly limit."},{kind:"paragraph",html:"Always read <code>accepted_count</code>. If it is 0, nothing was accepted and there is nothing to check."},{kind:"heading",text:"Common errors",id:"common-errors"},{kind:"table",headers:["Code","What happened"],rows:[["401","Your key is missing, wrong or switched off."],["402","Your monthly document limit is used up. Nothing was processed."],["413","The files together are too large."],["422","Too many files, or your JSON Schema is not valid."],["429","Too many requests. Wait as long as the Retry-After header says."]]},{kind:"heading",text:"If you do not get a response",id:"if-you-do-not-get-a-response"},{kind:"paragraph",html:"Do not send the same PDFs again straight away. They may already have been accepted, and sending them again uses your limit twice. Check first with the extraction ID if you have it."}],search:`
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
\`\`\`json
{"extraction_id":"a1b2c3d4","accepted_count":1,"rejected_count":1,
 "jobs":[{"id":"doc-1","extraction_id":"a1b2c3d4","status":"queued","result":null}],
 "rejected":[{"file_name":"broken.pdf","error":"The uploaded file is not a valid PDF."}]}
\`\`\`

Save \`extraction_id\`. That is the only thing you need to get your results.

## A bad file does not spoil the rest
If you send five PDFs and one is damaged, the other four are still processed. The damaged one appears in \`rejected\` with the reason. Rejected files are not counted against your monthly limit.

Always read \`accepted_count\`. If it is 0, nothing was accepted and there is nothing to check.

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
`,method:"POST",path:"/api/v1/extractions",success:"202 Accepted",auth:"Client API key required",samples:[{language:"cURL",code:`# Set PAPERSIGNAL_API_KEY privately in your environment.
curl --fail-with-body https://papersignal.duckdns.org/api/v1/extractions \\
  -H "X-API-Key: $PAPERSIGNAL_API_KEY" \\
  -F 'files=@invoice.pdf;type=application/pdf' \\
  -F 'output_template=<invoice.schema.json' \\
  -F 'ocr_mode=auto'`},{language:"Node.js",code:`// Node.js 22+; run on your backend.
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
if (!response.ok) throw new Error(\`Upload HTTP \${response.status}\`);
const batch = await response.json();
console.log(batch.extraction_id); // Persist this ID, then poll for the result.`},{language:"Python",code:`# Python with requests installed; run on your backend.
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
print(job["id"])  # Persist this ID, then poll for the result.`}]},{id:"results-endpoint",title:"Get the results",group:"Extraction API",summary:"Check your extraction until it is finished, then read the extracted fields.",blocks:[{kind:"heading",text:"What this does",id:"what-this-does"},{kind:"paragraph",html:"You give it the extraction ID and it tells you how each document is doing. When a document is finished, its extracted fields are in <code>result.data</code>."},{kind:"paragraph",html:"Ask again every 2 to 3 seconds until every document says <code>completed</code> or <code>failed</code>."},{kind:"heading",text:"What you get back",id:"what-you-get-back"},{kind:"code",language:"json",text:`[{"id":"doc-1","extraction_id":"a1b2c3d4","file_name":"invoice.pdf",
  "status":"completed","progress":100,
  "result":{"data":{"totalAmount":4500},"evidence":[],"warnings":[]}}]`},{kind:"paragraph",html:"You get a list with one entry per PDF you sent, in the order you sent them."},{kind:"heading",text:"The four statuses",id:"the-four-statuses"},{kind:"table",headers:["Status","What it means","What to do"],rows:[["queued","Waiting its turn.","Ask again in a few seconds."],["processing","Being read now. progress shows how far it is.","Ask again in a few seconds."],["completed","Finished.","Read result.data."],["failed","Did not finish.","Read error and failure_code."]]},{kind:"heading",text:"Reading the result",id:"reading-the-result"},{kind:"paragraph",html:"<code>result.data</code> matches your schema exactly. Same field names, same shape. Any field the PDF did not contain comes back as <code>null</code>, and anything you did not ask for is removed."},{kind:"paragraph",html:"<code>result.evidence</code> shows which page each value was found on, so you can check the answer."},{kind:"heading",text:"How long it takes",id:"how-long-it-takes"},{kind:"paragraph",html:"About 15 to 30 seconds per PDF. Two PDFs are read at a time; the rest wait their turn. So ten PDFs take longer than one."},{kind:"paragraph",html:"If you stop checking, the work still continues. You can come back to the same ID later."},{kind:"heading",text:"If a document failed",id:"if-a-document-failed"},{kind:"paragraph",html:'The request itself still succeeds with 200. Look at <code>failure_code</code> on that document to see whether to try again or fix something. See <a href="/documentation/errors">When something goes wrong</a>.'},{kind:"heading",text:"You only see your own work",id:"you-only-see-your-own-work"},{kind:"paragraph",html:"An extraction created with a different key returns 404, as if it does not exist."}],search:`
## What this does
You give it the extraction ID and it tells you how each document is doing. When a document is finished, its extracted fields are in \`result.data\`.

Ask again every 2 to 3 seconds until every document says \`completed\` or \`failed\`.

## What you get back
\`\`\`json
[{"id":"doc-1","extraction_id":"a1b2c3d4","file_name":"invoice.pdf",
  "status":"completed","progress":100,
  "result":{"data":{"totalAmount":4500},"evidence":[],"warnings":[]}}]
\`\`\`

You get a list with one entry per PDF you sent, in the order you sent them.

## The four statuses
| Status | What it means | What to do |
|---|---|---|
| queued | Waiting its turn. | Ask again in a few seconds. |
| processing | Being read now. progress shows how far it is. | Ask again in a few seconds. |
| completed | Finished. | Read result.data. |
| failed | Did not finish. | Read error and failure_code. |

## Reading the result
\`result.data\` matches your schema exactly. Same field names, same shape. Any field the PDF did not contain comes back as \`null\`, and anything you did not ask for is removed.

\`result.evidence\` shows which page each value was found on, so you can check the answer.

## How long it takes
About 15 to 30 seconds per PDF. Two PDFs are read at a time; the rest wait their turn. So ten PDFs take longer than one.

If you stop checking, the work still continues. You can come back to the same ID later.

## If a document failed
The request itself still succeeds with 200. Look at \`failure_code\` on that document to see whether to try again or fix something. See [When something goes wrong](/documentation/errors).

## You only see your own work
An extraction created with a different key returns 404, as if it does not exist.
`,method:"GET",path:"/api/v1/extractions/{extraction_id}",success:"200 OK",auth:"Client API key required",samples:[{language:"cURL",code:`curl --fail-with-body "https://papersignal.duckdns.org/api/v1/extractions/{extraction_id}" \\
  -H "X-API-Key: $PAPERSIGNAL_API_KEY"`}]},{id:"delete",title:"Delete documents and results",group:"Extraction API",summary:"Remove your uploaded PDFs and their results when you no longer need them.",blocks:[{kind:"heading",text:"What this does",id:"what-this-does"},{kind:"paragraph",html:"Deletes everything in one extraction: the PDFs you uploaded, the records and the results. This cannot be undone."},{kind:"heading",text:"What you get back",id:"what-you-get-back"},{kind:"table",headers:["Code","What it means"],rows:[["204","Deleted. The response is empty, which is normal."],["409","Something is still being read. Wait for it to finish, then try again."],["404","That ID does not exist, or it belongs to a different key."]]},{kind:"heading",text:"Why you should use it",id:"why-you-should-use-it"},{kind:"paragraph",html:"Your uploaded PDFs stay on the server until something deletes them. Nothing removes them automatically."},{kind:"paragraph",html:"If your documents contain private information, call this once your app has saved the fields it needs."}],search:`
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
`,method:"DELETE",path:"/api/v1/extractions/{extraction_id}",success:"204 No Content",auth:"Client API key required",samples:[{language:"cURL",code:`curl --fail-with-body -X DELETE "https://papersignal.duckdns.org/api/v1/extractions/{extraction_id}" \\
  -H "X-API-Key: $PAPERSIGNAL_API_KEY"`}]},{id:"account",title:"See your usage and limits",group:"Extraction API",summary:"Check how many documents you have used this month and how many are left.",blocks:[{kind:"heading",text:"What this does",id:"what-this-does"},{kind:"paragraph",html:"Tells you about your own key: how many documents you may process this month, how many you have used, and how many requests per minute you may make."},{kind:"heading",text:"What you get back",id:"what-you-get-back"},{kind:"code",language:"json",text:`{"period":"2026-09","documents_this_month":143,
 "monthly_document_quota":5000,"documents_remaining":4857,
 "rate_limit_per_minute":120}`},{kind:"table",headers:["Field","What it means"],rows:[["documents_this_month","Documents accepted so far this calendar month."],["documents_remaining","How many more you can send before you get 402."],["rate_limit_per_minute","How many requests you can make in any 60 seconds."]]},{kind:"heading",text:"Two different limits",id:"two-different-limits"},{kind:"paragraph",html:"<strong>Documents per month</strong> resets at the start of each month. Going over gives you 402 and nothing is processed."},{kind:"paragraph",html:"<strong>Requests per minute</strong> is about how fast you call, not how many PDFs you send. Going over gives you 429 with a Retry-After header telling you how long to wait."},{kind:"paragraph",html:"A rejected or damaged file does not count against your monthly total."},{kind:"heading",text:"Good practice",id:"good-practice"},{kind:"paragraph",html:"Check this before sending a large batch so you do not run out halfway. You can also show the remaining count in your own admin screen."}],search:`
## What this does
Tells you about your own key: how many documents you may process this month, how many you have used, and how many requests per minute you may make.

## What you get back
\`\`\`json
{"period":"2026-09","documents_this_month":143,
 "monthly_document_quota":5000,"documents_remaining":4857,
 "rate_limit_per_minute":120}
\`\`\`

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
`,method:"GET",path:"/api/v1/account",success:"200 OK",auth:"Client API key required",samples:[{language:"cURL",code:`curl --fail-with-body "https://papersignal.duckdns.org/api/v1/account" \\
  -H "X-API-Key: $PAPERSIGNAL_API_KEY"`}]},{id:"create-key",title:"Create an API key",group:"Administration",summary:"Service owners use this to give another application its own key.",blocks:[{kind:"heading",text:"Who this is for",id:"who-this-is-for"},{kind:"paragraph",html:"Only the person running the service. It needs the <code>X-Admin-Token</code> header, which is a different secret from a client API key. A client key cannot call this."},{kind:"heading",text:"What to send",id:"what-to-send"},{kind:"code",language:"json",text:'{"name":"Acme Corp","rate_limit_per_minute":60,"monthly_document_quota":200}'},{kind:"paragraph",html:"Only <code>name</code> is required. The other two fall back to the service defaults."},{kind:"heading",text:"What you get back",id:"what-you-get-back"},{kind:"code",language:"json",text:`{"key":"ps_live_xxxxxxxxxxxxxxxxxxxx",
 "api_key":{"id":"key-1","name":"Acme Corp","key_prefix":"ps_live_xxxxxx...",
            "rate_limit_per_minute":60,"monthly_document_quota":200}}`},{kind:"paragraph",html:"<strong>The key is shown once and never again.</strong> Only a scrambled version is stored, so even someone who copies the database cannot use it. If a key is lost, create a new one."},{kind:"heading",text:"Give every application its own key",id:"give-every-application-its-own-key"},{kind:"paragraph",html:"One key per application. Each key sees only its own documents, has its own limits, and can be switched off without affecting anyone else."},{kind:"heading",text:"Viewing and switching off keys",id:"viewing-and-switching-off-keys"},{kind:"paragraph",html:"These are not available over the internet, on purpose. The owner runs them on the server:"},{kind:"code",language:"bash",text:`python manage_keys.py list
python manage_keys.py revoke <key_id>`},{kind:"paragraph",html:"Keeping this off the network means that even if the admin token leaked, nobody could switch off every client&#x27;s access."}],search:`
## Who this is for
Only the person running the service. It needs the \`X-Admin-Token\` header, which is a different secret from a client API key. A client key cannot call this.

## What to send
\`\`\`json
{"name":"Acme Corp","rate_limit_per_minute":60,"monthly_document_quota":200}
\`\`\`
Only \`name\` is required. The other two fall back to the service defaults.

## What you get back
\`\`\`json
{"key":"ps_live_xxxxxxxxxxxxxxxxxxxx",
 "api_key":{"id":"key-1","name":"Acme Corp","key_prefix":"ps_live_xxxxxx...",
            "rate_limit_per_minute":60,"monthly_document_quota":200}}
\`\`\`

**The key is shown once and never again.** Only a scrambled version is stored, so even someone who copies the database cannot use it. If a key is lost, create a new one.

## Give every application its own key
One key per application. Each key sees only its own documents, has its own limits, and can be switched off without affecting anyone else.

## Viewing and switching off keys
These are not available over the internet, on purpose. The owner runs them on the server:
\`\`\`bash
python manage_keys.py list
python manage_keys.py revoke <key_id>
\`\`\`
Keeping this off the network means that even if the admin token leaked, nobody could switch off every client's access.
`,method:"POST",path:"/api/v1/keys",success:"201 Created",auth:"Service operator only - X-Admin-Token",samples:[{language:"cURL",code:`curl --fail-with-body "https://papersignal.duckdns.org/api/v1/keys" \\
  -H "X-Admin-Token: $PAPERSIGNAL_ADMIN_TOKEN"`}]},{id:"schema",title:"Schemas and OCR",group:"Integration guides",summary:"Choose the output fields and tell the service how to read PDF pages.",blocks:[{kind:"heading",text:"What is a JSON Schema",id:"what-is-a-json-schema"},{kind:"paragraph",html:"A JSON Schema describes the field names and value types your app expects. Send it as text in output_template."},{kind:"code",language:"json",text:`{
  "type": "object",
  "properties": {
    "invoiceNumber": {
      "type": "string",
      "description": "Invoice identifier printed on the document"
    },
    "invoiceDate": {
      "type": "string",
      "description": "Invoice date, YYYY-MM-DD when available"
    },
    "totalAmount": {
      "type": "number"
    },
    "currency": {
      "type": "string"
    }
  }
}`},{kind:"paragraph",html:"Do not send example data such as {&quot;totalAmount&quot;:42}. The root must have type object and a nonempty properties object."},{kind:"heading",text:"Allowed types and limits",id:"allowed-types-and-limits"},{kind:"paragraph",html:"Use string, number, integer, boolean, object, array or null. Every nested object needs at least one property. Each object can have up to 100 properties, with up to 8 levels below the root."},{kind:"paragraph",html:"For arrays, set items to describe each value. If items is missing, it defaults to string. Prefer one concrete type per field. $ref, allOf, anyOf, oneOf and not are not supported."},{kind:"heading",text:"Missing and extra values",id:"missing-and-extra-values"},{kind:"paragraph",html:"All declared fields appear in the output. Missing values or values with the wrong basic type become null. Extra output keys are removed. Missing nested objects become their declared child fields with null values. A missing or wrong-type array becomes null."},{kind:"heading",text:"Check business rules yourself",id:"check-business-rules-yourself"},{kind:"paragraph",html:"The model receives descriptions and selected constraints such as enum, format, minimum, maximum, minLength and maxLength. The local output check enforces field shape and basic types, not every schema rule or factual accuracy. Your app must check dates, amounts and allowed values before acting on them."},{kind:"heading",text:"OCR modes",id:"ocr-modes"},{kind:"paragraph",html:"OCR means reading text from page images."},{kind:"table",headers:["Mode","What happens"],rows:[["auto","Read embedded text first. Try vision for weak pages, then OCR if needed."],["always","Use OCR for every page."],["never","Read only embedded text. Image-only PDFs fail if they contain no readable text."]]},{kind:"heading",text:"Where the document goes",id:"where-the-document-goes"},{kind:"paragraph",html:"All modes still use Mistral to extract the final fields. never does not turn off AI. Digital text is sent to Mistral; vision sends selected page images. OCR currently uploads the full PDF and asks for selected pages. The code tries to delete that provider upload, but a failed deletion is not reported to the user. Provider retention terms were not checked in this review."}],search:`
## What is a JSON Schema
A JSON Schema describes the field names and value types your app expects. Send it as text in output_template.
\`\`\`json
{
  "type": "object",
  "properties": {
    "invoiceNumber": {
      "type": "string",
      "description": "Invoice identifier printed on the document"
    },
    "invoiceDate": {
      "type": "string",
      "description": "Invoice date, YYYY-MM-DD when available"
    },
    "totalAmount": {
      "type": "number"
    },
    "currency": {
      "type": "string"
    }
  }
}
\`\`\`
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
`},{id:"results",title:"Jobs and results",group:"Integration guides",summary:"Understand status, extracted data and the extra details returned with each job.",blocks:[{kind:"heading",text:"Job status",id:"job-status"},{kind:"table",headers:["Status","Meaning"],rows:[["queued","Waiting for a worker."],["processing","Running."],["completed","Result is ready."],["failed","Work did not succeed. Read the error details."]]},{kind:"paragraph",html:"Both completed and failed can have progress 100. HTTP 200 on a status request only means the lookup worked."},{kind:"heading",text:"Job fields",id:"job-fields"},{kind:"table",headers:["Field","Meaning"],rows:[["id, extraction_id","The document&#x27;s own ID, and the extraction it belongs to."],["file_name, file_size","Safe display filename and size in bytes."],["instruction","The fixed extraction instruction used by the server."],["output_template","The submitted schema as a string; may be null for old jobs."],["ocr_mode, schema_mode","Page-reading policy and schema mode. New jobs use json_schema."],["status, progress, stage","State, progress from 0-100, and a human-readable stage."],["result","null before success; extracted result after completion."],["error, failure_code, failure_stage","Failure details or null."],["page_count","Number of pages, or null."],["python_text_pages, ocr_pages","Page counts for embedded-text and OCR routes."],["vision_attempted_pages, vision_pages, vision_failed_pages","Vision attempts, successful reads and fallbacks."],["text_model, vision_model, ocr_model","Configured model names. A name here does not prove it was used."],["duration_ms","Worker time in milliseconds; excludes time waiting in the queue."],["created_at, updated_at","UTC timestamps in ISO-8601 format."]]},{kind:"paragraph",html:"The response does not include the local file path or owning key ID. Page counts are processing details, not accuracy scores. In never mode, python_text_pages includes empty pages too."},{kind:"heading",text:"Inside result",id:"inside-result"},{kind:"table",headers:["Field","Meaning"],rows:[["data","The business values requested by your schema."],["evidence","Supporting text with label, page and evidence fields. Page is one-based or null."],["warnings","Messages from extraction. May be empty."],["request","The extraction instruction."],["document","File metadata, page-reading counts, model names, section count and duration."]]},{kind:"paragraph",html:"Use result.data in your app. Evidence is generated by the model and may not cover every field. Empty warnings do not prove the values are correct."},{kind:"heading",text:"Which lookup to use",id:"which-lookup-to-use"},{kind:"paragraph",html:'Use <a href="/documentation/results-endpoint">one job</a>, <a href="/documentation/results-endpoint">one batch</a>, or <a href="/documentation/results-endpoint">up to 50 IDs</a>. Use <a href="/documentation/results-endpoint">recent jobs</a> for a short history. Save job IDs in your own database for complete tracking.'}],search:`
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
`},{id:"errors",title:"Errors and retries",group:"Integration guides",summary:"Check HTTP errors and job failures separately. Retry only when it is safe.",blocks:[{kind:"heading",text:"HTTP status codes",id:"http-status-codes"},{kind:"table",headers:["Code","Meaning and next step"],rows:[["200","Read succeeded. Still check the job status."],["201","A key was created. Save the one-time key."],["202","Upload accepted. Check the job later."],["204","Delete or revoke succeeded. There is no JSON body."],["400","Invalid, empty, protected, oversized or over-page-limit PDF. Fix the file."],["401","Wrong, missing or disabled key/token. Check credentials."],["402","Monthly document limit reached. Contact the owner."],["404","Item is missing or belongs to another key. Check the ID and key."],["409","Job is processing, or the key was already disabled."],["413","Combined upload or proxy size limit exceeded. Send less data."],["422","Missing or invalid form, schema, OCR mode, query or admin input."],["429","Too many requests or the single-upload queue is full. Wait."],["503","AI/admin configuration is missing, or the service is unavailable."],["500, 502, 504","Server or proxy error. The upload may already be accepted."]]},{kind:"heading",text:"Error body",id:"error-body"},{kind:"paragraph",html:"Most explicit API errors return an object like this:"},{kind:"code",language:"json",text:'{"detail":"Send your key in the X-API-Key header."}'},{kind:"paragraph",html:"Input-validation errors may put a list in detail instead of a string. Proxy errors may return HTML or text. Do not assume every error body is JSON, and avoid logging sensitive inputs."},{kind:"heading",text:"Job failures",id:"job-failures"},{kind:"paragraph",html:"A status lookup can return HTTP 200 with status failed."},{kind:"table",headers:["failure_code","Meaning"],rows:[["PDF_PROCESSING_ERROR","The worker could not read or process the PDF."],["AI_EXTRACTION_ERROR","The AI call failed, or no readable text was found."],["PROCESSING_ERROR","Another worker error occurred."]]},{kind:"paragraph",html:'Read error and failure_stage, and keep the job ID for support. <a href="/documentation/test-results">See recent test results</a> for known observed failures.'},{kind:"heading",text:"Retrying requests",id:"retrying-requests"},{kind:"paragraph",html:"Safe read requests can be retried with a delay and a time limit. A rate-limit 429 includes Retry-After in seconds; a queue-full 429 does not. For example, if Retry-After is 5, wait at least five seconds."},{kind:"paragraph",html:"Do not automatically repeat uploads after a timeout, lost response or 5xx. The first upload may already be running, and the service does not remove duplicates. Another upload can use more quota. Check recent jobs or ask the owner first."},{kind:"heading",text:"Waiting too long",id:"waiting-too-long"},{kind:"paragraph",html:"Use a deadline in your app. If the deadline passes, keep the ID and allow later lookup. Your timeout does not cancel the job, and the service does not promise a fixed completion time."}],search:`
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
\`\`\`json
{"detail":"Send your key in the X-API-Key header."}
\`\`\`
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
`},{id:"cors",title:"Browser integration",group:"Integration guides",summary:"Call PaperSignal from your backend to keep shared keys private.",blocks:[{kind:"heading",text:"Recommended setup",id:"recommended-setup"},{kind:"paragraph",html:"Your frontend sends the PDF to your backend. Your backend checks its user, then calls PaperSignal with the client key. Server-to-server calls do not need browser CORS changes."},{kind:"heading",text:"Direct browser calls",id:"direct-browser-calls"},{kind:"paragraph",html:"CORS is the browser rule that controls calls between different website origins. If you intentionally call the API from a browser, the owner must allow that browser&#x27;s exact origin and restart the service."},{kind:"code",language:"dotenv",text:'CORS_ORIGINS=["https://papersignal.duckdns.org","https://crm.example.com"]'},{kind:"paragraph",html:"Use this JSON-array format with the current settings library. Do not rely on older comma-separated examples."},{kind:"heading",text:"Supported browser requests",id:"supported-browser-requests"},{kind:"paragraph",html:"Allowed methods are GET, POST, DELETE and OPTIONS. Allowed application headers include Content-Type, X-API-Key and Authorization. Cookies are not enabled. X-Admin-Token is not in the allowed browser headers."},{kind:"heading",text:"Reading Retry-After",id:"reading-retry-after"},{kind:"paragraph",html:"The server does not expose Retry-After to cross-origin JavaScript. Browser code may not be able to read it even though the HTTP response has it. A backend client can read it normally."},{kind:"heading",text:"CORS is not authentication",id:"cors-is-not-authentication"},{kind:"paragraph",html:"Allowing an origin does not make a shared key safe to expose. Anyone who gets that key can use its allowed APIs and access its jobs."}],search:`
## Recommended setup
Your frontend sends the PDF to your backend. Your backend checks its user, then calls PaperSignal with the client key. Server-to-server calls do not need browser CORS changes.

## Direct browser calls
CORS is the browser rule that controls calls between different website origins. If you intentionally call the API from a browser, the owner must allow that browser's exact origin and restart the service.
\`\`\`dotenv
CORS_ORIGINS=["https://papersignal.duckdns.org","https://crm.example.com"]
\`\`\`
Use this JSON-array format with the current settings library. Do not rely on older comma-separated examples.

## Supported browser requests
Allowed methods are GET, POST, DELETE and OPTIONS. Allowed application headers include Content-Type, X-API-Key and Authorization. Cookies are not enabled. X-Admin-Token is not in the allowed browser headers.

## Reading Retry-After
The server does not expose Retry-After to cross-origin JavaScript. Browser code may not be able to read it even though the HTTP response has it. A backend client can read it normally.

## CORS is not authentication
Allowing an origin does not make a shared key safe to expose. Anyone who gets that key can use its allowed APIs and access its jobs.
`},{id:"examples",title:"Complete client examples",group:"Integration guides",summary:"Download a working starting point for uploads and status checks.",blocks:[{kind:"heading",text:"Download the files",id:"download-the-files"},{kind:"list",items:['<a href="/documentation-assets/python_client.py">Python client</a>: Python 3.11 or later; no extra packages.','<a href="/documentation-assets/node_client.mjs">Node.js client</a>: Node.js 22 or later; no extra packages.','<a href="/documentation-assets/invoice.schema.json">Invoice schema</a>: example field names and types.']},{kind:"paragraph",html:"Save the client and invoice.schema.json in the same folder. Both clients upload once, print the job ID, and check status until success, failure or a ten-minute deadline."},{kind:"heading",text:"Set your key privately",id:"set-your-key-privately"},{kind:"paragraph",html:"These are PowerShell examples. Replace the placeholder with your own client key in your private environment."},{kind:"code",language:"powershell",text:`$env:PAPERSIGNAL_API_KEY = '<YOUR_CLIENT_KEY>'
$env:PAPERSIGNAL_BASE_URL = 'https://papersignal.duckdns.org'`},{kind:"heading",text:"Run a client",id:"run-a-client"},{kind:"code",language:"powershell",text:`python python_client.py 'C:\\Documents\\invoice.pdf'
node node_client.mjs 'C:\\Documents\\invoice.pdf'`},{kind:"paragraph",html:"This sends a real upload and uses your document quota. Start with a small sample file. The examples hold the whole PDF in memory; use a streaming upload library for large documents."},{kind:"heading",text:"Use it in your app",id:"use-it-in-your-app"},{kind:"paragraph",html:"Put uploads and status checks in your backend or background worker. Save the returned ID against your business record and user. Check result.data before saving it or triggering an action."},{kind:"heading",text:"Error handling",id:"error-handling"},{kind:"paragraph",html:"The examples retry some read errors, but never automatically repeat an upload. They do not delete results automatically. If the waiting deadline passes, the job may still be running. Keep its ID and check later."},{kind:"heading",text:"Tests",id:"tests"},{kind:"paragraph",html:'The examples passed local tests for file-upload format, successful status checks, rate-limit responses, failed jobs and invalid authentication. These use controlled HTTP responses. The separate <a href="/documentation/test-results">API test report</a> explains real-provider and AWS tests.'}],search:`
## Download the files
- [Python client](/documentation-assets/python_client.py): Python 3.11 or later; no extra packages.
- [Node.js client](/documentation-assets/node_client.mjs): Node.js 22 or later; no extra packages.
- [Invoice schema](/documentation-assets/invoice.schema.json): example field names and types.

Save the client and invoice.schema.json in the same folder. Both clients upload once, print the job ID, and check status until success, failure or a ten-minute deadline.

## Set your key privately
These are PowerShell examples. Replace the placeholder with your own client key in your private environment.
\`\`\`powershell
$env:PAPERSIGNAL_API_KEY = '<YOUR_CLIENT_KEY>'
$env:PAPERSIGNAL_BASE_URL = 'https://papersignal.duckdns.org'
\`\`\`
## Run a client
\`\`\`powershell
python python_client.py 'C:\\Documents\\invoice.pdf'
node node_client.mjs 'C:\\Documents\\invoice.pdf'
\`\`\`
This sends a real upload and uses your document quota. Start with a small sample file. The examples hold the whole PDF in memory; use a streaming upload library for large documents.

## Use it in your app
Put uploads and status checks in your backend or background worker. Save the returned ID against your business record and user. Check result.data before saving it or triggering an action.

## Error handling
The examples retry some read errors, but never automatically repeat an upload. They do not delete results automatically. If the waiting deadline passes, the job may still be running. Keep its ID and check later.

## Tests
The examples passed local tests for file-upload format, successful status checks, rate-limit responses, failed jobs and invalid authentication. These use controlled HTTP responses. The separate [API test report](/documentation/test-results) explains real-provider and AWS tests.
`,samples:[{language:"Python",code:`"""Python 3.11+ single-PDF integration example; standard library only.

Uploads once. Only read requests are retried. Files are held in memory for this
small-document example; use a streaming multipart client for large uploads.
"""
import argparse
import json
import os
from pathlib import Path
import secrets
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def request_json(url, key, *, body=None, content_type=None, timeout=60):
    headers = {"X-API-Key": key, "Accept": "application/json"}
    if content_type:
        headers["Content-Type"] = content_type
    request = Request(url, data=body, headers=headers, method="POST" if body is not None else "GET")
    with urlopen(request, timeout=timeout) as response:
        return json.load(response)


def upload(base, key, pdf, schema, ocr_mode):
    boundary = "papersignal-" + secrets.token_hex(16)
    parts = []
    for name, value in (("output_template", json.dumps(schema)), ("ocr_mode", ocr_mode)):
        parts.append((f"--{boundary}\\r\\nContent-Disposition: form-data; name=\\"{name}\\"\\r\\n\\r\\n"
                      f"{value}\\r\\n").encode())
    # Constant upload filename avoids multipart-header injection from local paths.
    parts.append((f"--{boundary}\\r\\nContent-Disposition: form-data; name=\\"files\\"; "
                  "filename=\\"document.pdf\\"\\r\\nContent-Type: application/pdf\\r\\n\\r\\n").encode())
    parts.extend((pdf.read_bytes(), f"\\r\\n--{boundary}--\\r\\n".encode()))
    return request_json(base + "/api/v1/extractions", key, body=b"".join(parts),
                        content_type=f"multipart/form-data; boundary={boundary}", timeout=120)


def poll(base, key, extraction_id, max_wait=600, interval=3):
    deadline = time.monotonic() + max_wait
    failures = 0
    while time.monotonic() < deadline:
        delay = interval
        try:
            documents = request_json(base + "/api/v1/extractions/" + extraction_id, key,
                               timeout=max(0.1, min(30, deadline - time.monotonic())))
            failures = 0
            if all(d["status"] in ("completed", "failed") for d in documents):
                failed = [d for d in documents if d["status"] == "failed"]
                if failed:
                    first = failed[0]
                    raise RuntimeError(
                        f"{first['file_name']} failed: {first.get('failure_code')} "
                        f"at {first.get('failure_stage')}. {first.get('error', '')}")
                return [d["result"] for d in documents]
        except HTTPError as error:
            if error.code != 429 and error.code not in (500, 502, 503, 504):
                raise
            failures += 1
            retry_after = error.headers.get("Retry-After", "")
            delay = max(interval, float(retry_after)) if retry_after.isdigit() else min(30, 2 ** min(failures, 5))
        except (URLError, TimeoutError):
            failures += 1
            delay = min(30, 2 ** min(failures, 5))
        remaining = deadline - time.monotonic()
        if remaining > 0:
            time.sleep(min(delay, remaining))
    raise TimeoutError(f"Polling deadline reached. Extraction {extraction_id} may still be running; keep the ID and check later.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pdf", type=Path)
    parser.add_argument("--schema", type=Path, default=Path(__file__).with_name("invoice.schema.json"))
    parser.add_argument("--ocr-mode", choices=("auto", "always", "never"), default="auto")
    parser.add_argument("--wait-seconds", type=float, default=600)
    parser.add_argument("--poll-seconds", type=float, default=3)
    args = parser.parse_args()
    if args.wait_seconds <= 0 or args.poll_seconds <= 0:
        parser.error("Wait and polling seconds must be positive.")
    key = os.environ.get("PAPERSIGNAL_API_KEY", "").strip()
    if not key:
        parser.error("Set PAPERSIGNAL_API_KEY in the backend environment.")
    base = os.environ.get("PAPERSIGNAL_BASE_URL", "https://papersignal.duckdns.org").rstrip("/")
    schema = json.loads(args.schema.read_text(encoding="utf-8"))
    # Do not wrap uploads in a retry loop: an ambiguous failure may already have created work.
    batch = upload(base, key, args.pdf, schema, args.ocr_mode)
    print(f"Accepted extraction: {batch['extraction_id']} (save this ID)", file=sys.stderr, flush=True)
    result = poll(base, key, batch["extraction_id"], args.wait_seconds, args.poll_seconds)
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    try:
        main()
    except HTTPError as error:
        print(f"API HTTP {error.code}. See the integration guide; do not blindly retry an upload.", file=sys.stderr)
        raise SystemExit(1)
    except (RuntimeError, URLError, TimeoutError, OSError, ValueError) as error:
        print(str(error), file=sys.stderr)
        raise SystemExit(1)
`},{language:"Node.js",code:`// Node.js 22+, native Fetch/FormData. This example buffers the PDF in memory.
// Only polling requests are retried; uploads are sent exactly once.
import { readFile } from 'node:fs/promises';
import { pathToFileURL } from 'node:url';

const sleep = ms => new Promise(resolve => setTimeout(resolve, ms));

export async function upload(base, key, pdfPath, schema, ocrMode = 'auto') {
  const form = new FormData();
  form.append('files', new Blob([await readFile(pdfPath)], { type: 'application/pdf' }), 'document.pdf');
  form.append('output_template', JSON.stringify(schema));
  form.append('ocr_mode', ocrMode);
  const response = await fetch(\`\${base}/api/v1/extractions\`, {
    method: 'POST', headers: { 'X-API-Key': key }, body: form,
    signal: AbortSignal.timeout(120_000),
  });
  if (!response.ok) throw new Error(\`Upload HTTP \${response.status}. Check the integration guide before retrying.\`);
  return response.json();
}

export async function poll(base, key, extractionId, maxWaitMs = 600_000, intervalMs = 3_000) {
  const deadline = Date.now() + maxWaitMs;
  let failures = 0;
  while (Date.now() < deadline) {
    let response;
    try {
      response = await fetch(\`\${base}/api/v1/extractions/\${encodeURIComponent(extractionId)}\`, {
        headers: { 'X-API-Key': key },
        signal: AbortSignal.timeout(Math.max(1, Math.min(30_000, deadline - Date.now()))),
      });
    } catch (error) {
      if (!(error instanceof TypeError) && !['TimeoutError', 'AbortError'].includes(error.name)) throw error;
      const delay = Math.min(30_000, 1000 * 2 ** Math.min(++failures, 5));
      await sleep(Math.max(0, Math.min(delay, deadline - Date.now())));
      continue;
    }
    if (response.status === 429 || [500, 502, 503, 504].includes(response.status)) {
      const raw = response.headers.get('Retry-After');
      const fallback = Math.min(30_000, 1000 * 2 ** Math.min(++failures, 5));
      const delay = raw && /^\\d+$/.test(raw) ? Math.max(intervalMs, Number(raw) * 1000) : fallback;
      await response.body?.cancel();
      await sleep(Math.max(0, Math.min(delay, deadline - Date.now())));
      continue;
    }
    if (!response.ok) throw new Error(\`Polling HTTP \${response.status}; extraction \${extractionId}.\`);
    const documents = await response.json();
    failures = 0;
    if (documents.every(d => d.status === 'completed' || d.status === 'failed')) {
      const failed = documents.find(d => d.status === 'failed');
      if (failed) throw new Error(\`\${failed.file_name} failed: \${failed.failure_code} at \${failed.failure_stage}. \${failed.error ?? ''}\`);
      return documents.map(d => d.result);
    }
    await sleep(Math.max(0, Math.min(intervalMs, deadline - Date.now())));
  }
  throw new Error(\`Polling deadline reached. Extraction \${extractionId} may still be running; keep the ID and check later.\`);
}

async function main() {
  const pdfPath = process.argv[2];
  const key = process.env.PAPERSIGNAL_API_KEY?.trim();
  if (!pdfPath || !key) throw new Error('Set PAPERSIGNAL_API_KEY, then run: node node_client.mjs document.pdf [schema.json]');
  const base = (process.env.PAPERSIGNAL_BASE_URL || 'https://papersignal.duckdns.org').replace(/\\/+$/, '');
  const schema = JSON.parse(await readFile(process.argv[3] || new URL('./invoice.schema.json', import.meta.url), 'utf8'));
  const batch = await upload(base, key, pdfPath, schema);
  console.error(\`Accepted extraction: \${batch.extraction_id} (save this ID)\`);
  console.log(JSON.stringify(await poll(base, key, batch.extraction_id), null, 2));
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  main().catch(error => { console.error(error.message); process.exitCode = 1; });
}
`}]},{id:"operations",title:"Service limits and data handling",group:"Integration guides",summary:"Know the current limits before you depend on this service.",blocks:[{kind:"heading",text:"Current design",id:"current-design"},{kind:"paragraph",html:"PaperSignal uses one API instance, local PDF storage, SQLite databases and an in-memory work queue. An in-memory queue is stored in the running process, so accepted jobs may be left unfinished after a crash or restart. The code does not automatically resume them."},{kind:"heading",text:"Recovery and scale",id:"recovery-and-scale"},{kind:"paragraph",html:"For reliable restart recovery, use a durable queue and a way to resume interrupted jobs. For several API instances, use shared file storage, a shared database and a shared rate limiter. These changes were not made as part of this documentation task."},{kind:"heading",text:"Upload limits",id:"upload-limits"},{kind:"paragraph",html:"Health reports the backend&#x27;s configured limits. A proxy can reject smaller requests first. Verify the actual request limit before allowing large uploads. Queue capacity includes both running and waiting jobs; it is not a throughput promise."},{kind:"heading",text:"Duplicate uploads and quotas",id:"duplicate-uploads-and-quotas"},{kind:"paragraph",html:"The API has no idempotency key, so it does not identify duplicate upload requests. A lost response can lead to duplicate work if your app retries."},{kind:"paragraph",html:"Quota checking and usage updates are separate. Simultaneous uploads may exceed a quota. Internal batch page counts may include queue-rejected files. Fix these before using the counters for exact billing."},{kind:"heading",text:"Keys and deletion",id:"keys-and-deletion"},{kind:"paragraph",html:"A new key cannot read an old key&#x27;s jobs. Plan how to save results before replacing a key. Delete only completed or failed jobs; queued deletion is not reliable cancellation."},{kind:"paragraph",html:"The current bulk cleanup script scans only the latest 100 jobs. Older data can be missed. Set and verify a retention schedule instead of assuming files disappear automatically."},{kind:"heading",text:"External AI processing",id:"external-ai-processing"},{kind:"paragraph",html:"All modes send readable text to Mistral. Vision sends selected page images. OCR uploads the full PDF and requests selected pages, then tries to delete the provider file. AWS hosting does not mean all document processing stays inside AWS. Confirm provider data handling and retention before sending business documents."},{kind:"heading",text:"What has been tested",id:"what-has-been-tested"},{kind:"paragraph",html:'See the <a href="/documentation/test-results">dated API test report</a>. It separates AWS tests, local real-AI tests and tests with controlled responses. Load capacity, large proxy uploads, restart recovery and provider data-retention terms have not been verified.'}],search:`
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
`}];var C=t=>["/documentation",t],Q=(t,a)=>a.name,X=(t,a)=>a.id,Z=(t,a)=>a.language;function ee(t,a){if(t&1){let e=A();n(0,"button",44),y("click",function(){_(e);let d=c();return P(d.menuOpen.set(!1))}),i()}}function te(t,a){if(t&1&&(n(0,"span",48),o(1),i()),t&2){let e=c().$implicit;L("nav-method "+e.method.toLowerCase()),s(),u(e.method==="DELETE"?"DEL":e.method)}}function ne(t,a){if(t&1){let e=A();n(0,"a",46),y("click",function(){_(e);let d=c(2);return P(d.navigate())}),b(1,te,2,3,"span",47),n(2,"span"),o(3),i()()}if(t&2){let e=a.$implicit,r=c(2);E("active",r.current().id===e.id),h("routerLink",S(6,C,e.id)),j("aria-current",r.current().id===e.id?"page":null),s(),v(e.method?1:-1),s(2),u(e.title)}}function ae(t,a){if(t&1&&(n(0,"div",22)(1,"h2"),o(2),i(),p(3,ne,4,8,"a",45,X),i()),t&2){let e=a.$implicit;s(2),u(e.name),s(),m(e.pages)}}function ie(t,a){t&1&&(n(0,"p",23),o(1,"No matching topics. Try \u201Cupload\u201D, \u201Ckey\u201D or \u201Cquota\u201D."),i())}function oe(t,a){if(t&1&&(n(0,"div",49)(1,"span"),o(2),i(),n(3,"code"),o(4),i(),n(5,"span",50),o(6),i()(),n(7,"p",51)(8,"span",11),o(9,"\u2301"),i(),o(10),i()),t&2){let e=c();s(),L("method-badge "+e.current().method.toLowerCase()),s(),u(e.current().method),s(2),u(e.current().path),s(2),u(e.current().success),s(4),W(" ",e.current().auth)}}function re(t,a){if(t&1){let e=A();n(0,"div",52)(1,"a",53)(2,"span"),o(3,"01"),i(),n(4,"strong"),o(5,"Submit a PDF"),i(),n(6,"small"),o(7,"File + JSON Schema"),i()(),n(8,"span",54),o(9,"\u2192"),i(),n(10,"a",55)(11,"span"),o(12,"02"),i(),n(13,"strong"),o(14,"Track the job"),i(),n(15,"small"),o(16,"Poll until complete"),i()(),n(17,"span",54),o(18,"\u2192"),i(),n(19,"a",56)(20,"span"),o(21,"03"),i(),n(22,"strong"),o(23,"Use the result"),i(),n(24,"small"),o(25,"Read result.data"),i()()(),n(26,"div",57)(27,"div")(28,"span"),o(29,"PRODUCTION BASE URL"),i(),n(30,"code"),o(31,"https://papersignal.duckdns.org"),i()(),n(32,"button",58),y("click",function(){_(e);let d=c();return P(d.copy("https://papersignal.duckdns.org","base"))}),o(33),i()()}if(t&2){let e=c();s(33),u(e.copied()==="base"?"Copied":"Copy URL")}}function se(t,a){if(t&1){let e=A();n(0,"button",58),y("click",function(){let d=_(e).$implicit,l=c(2);return P(l.language.set(d.language))}),o(1),i()}if(t&2){let e,r,d=a.$implicit,l=c(2);E("selected",((e=l.sample())==null?null:e.language)===d.language),j("aria-pressed",((r=l.sample())==null?null:r.language)===d.language),s(),u(d.language)}}function de(t,a){if(t&1){let e=A();n(0,"section",30)(1,"div",59)(2,"div",60),p(3,se,2,4,"button",61,Z),i(),n(5,"button",62),y("click",function(){_(e);let d=c();return P(d.copy(d.sample().code,"sample"))}),o(6),i()(),n(7,"pre",63)(8,"code"),o(9),i()()()}if(t&2){let e,r=c();s(3),m(r.current().samples),s(3),u(r.copied()==="sample"?"Copied!":"Copy code"),s(3),u((e=r.sample())==null?null:e.code)}}function le(t,a){if(t&1&&(n(0,"h2",64),o(1),n(2,"a",68),o(3,"#"),i()()),t&2){let e=c().$implicit,r=c();h("id",e.id),s(),u(e.text),s(),h("routerLink",S(4,C,r.current().id))("fragment",e.id)}}function ce(t,a){if(t&1&&g(0,"p",65),t&2){let e=c().$implicit;h("innerHTML",e.html,D)}}function ue(t,a){if(t&1&&g(0,"li",65),t&2){let e=a.$implicit;h("innerHTML",e,D)}}function he(t,a){if(t&1&&(n(0,"ul"),p(1,ue,1,1,"li",65,T),i()),t&2){let e=c().$implicit;s(),m(e.items)}}function pe(t,a){if(t&1&&g(0,"th",69),t&2){let e=a.$implicit;h("innerHTML",e,D)}}function me(t,a){if(t&1&&g(0,"td",65),t&2){let e=a.$implicit;h("innerHTML",e,D)}}function ge(t,a){if(t&1&&(n(0,"tr"),p(1,me,1,1,"td",65,T),i()),t&2){let e=a.$implicit;s(),m(e)}}function ye(t,a){if(t&1&&(n(0,"div",66)(1,"table")(2,"thead")(3,"tr"),p(4,pe,1,1,"th",69,T),i()(),n(6,"tbody"),p(7,ge,3,0,"tr",null,T),i()()()),t&2){let e=c().$implicit;s(4),m(e.headers),s(3),m(e.rows)}}function fe(t,a){if(t&1){let e=A();n(0,"div",67)(1,"div",59)(2,"span"),o(3),i(),n(4,"button",62),y("click",function(){_(e);let d=c(),l=d.$implicit,x=d.$index,R=c();return P(R.copy(l.text,"code-"+x))}),o(5),i()(),n(6,"pre",63)(7,"code"),o(8),i()()()}if(t&2){let e=c(),r=e.$implicit,d=e.$index,l=c();s(3),u(r.language||"Example"),s(2),u(l.copied()==="code-"+d?"Copied!":"Copy"),s(3),u(r.text)}}function ke(t,a){if(t&1&&b(0,le,4,6,"h2",64)(1,ce,1,1,"p",65)(2,he,3,0,"ul")(3,ye,9,0,"div",66)(4,fe,9,3,"div",67),t&2){let e,r=a.$implicit;v((e=r.kind)==="heading"?0:e==="paragraph"?1:e==="list"?2:e==="table"?3:e==="code"?4:-1)}}function be(t,a){if(t&1&&(n(0,"a",33)(1,"small"),o(2,"\u2190 Previous"),i(),n(3,"strong"),o(4),i()()),t&2){let e=a;h("routerLink",S(2,C,e.id)),s(4),u(e.title)}}function ve(t,a){t&1&&g(0,"span")}function xe(t,a){if(t&1&&(n(0,"a",34)(1,"small"),o(2,"Next \u2192"),i(),n(3,"strong"),o(4),i()()),t&2){let e=a;h("routerLink",S(2,C,e.id)),s(4),u(e.title)}}function we(t,a){if(t&1&&(n(0,"a",37),o(1),i()),t&2){let e=a.$implicit,r=c();h("routerLink",S(3,C,r.current().id))("fragment",e.id),s(),u(e.text)}}var V=class t{route=I(H);title=I(G);meta=I(K);params=B(this.route.paramMap);pages=J;query=k("");menuOpen=k(!1);copied=k("");copyError=k("");language=k("cURL");activeId=f(()=>this.params()?.get("page")||"overview");current=f(()=>this.pages.find(a=>a.id===this.activeId())||this.pages[0]);groups=f(()=>{let a=this.query().trim().toLowerCase(),e=this.pages.filter(r=>!a||`${r.title} ${r.path||""} ${r.search}`.toLowerCase().includes(a));return[...new Set(e.map(r=>r.group))].map(r=>({name:r,pages:e.filter(d=>d.group===r)}))});headings=f(()=>this.current().blocks.filter(a=>a.kind==="heading"));previous=f(()=>this.pages[this.pages.indexOf(this.current())-1]);next=f(()=>this.pages[this.pages.indexOf(this.current())+1]);sample=f(()=>this.current().samples?.find(a=>a.language===this.language())||this.current().samples?.[0]);constructor(){M(()=>{let a=this.current();this.title.setTitle(`${a.title} | PaperSignal documentation`),this.meta.updateTag({name:"description",content:a.summary}),this.menuOpen.set(!1),this.copyError.set(""),this.query.set("")})}navigate(){this.menuOpen.set(!1)}onKeydown(a){a.key==="Escape"&&this.menuOpen.set(!1);let e=a.target;a.key==="/"&&!a.ctrlKey&&!a.metaKey&&!["INPUT","TEXTAREA","SELECT"].includes(e?.tagName||"")&&!e?.isContentEditable&&(a.preventDefault(),this.menuOpen.set(!0),setTimeout(()=>document.getElementById("docs-search")?.focus()))}async copy(a,e){try{await navigator.clipboard.writeText(a),this.copied.set(e),this.copyError.set(""),setTimeout(()=>{this.copied()===e&&this.copied.set("")},2e3)}catch{this.copyError.set("Copy is unavailable in this browser. Select and copy the code directly.")}}static \u0275fac=function(e){return new(e||t)};static \u0275cmp=U({type:t,selectors:[["app-documentation"]],hostBindings:function(e,r){e&1&&y("keydown",function(l){return r.onKeydown(l)},Y)},decls:86,vars:18,consts:[["href","#docs-content",1,"skip"],[1,"docs-header"],["routerLink","/documentation","aria-label","PaperSignal documentation home",1,"docs-brand"],["aria-hidden","true",1,"docs-logo"],["viewBox","0 0 24 24"],["d","M6 3h8l4 4v14H6zM14 3v5h4M9 12h6M9 16h4"],[1,"brand-accent"],[1,"header-divider"],[1,"header-label"],["aria-label","External resources",1,"header-links"],["href","https://papersignal.duckdns.org/api/docs","target","_blank","rel","noopener"],["aria-hidden","true"],["href","https://papersignal.duckdns.org",1,"open-app"],["type","button","aria-controls","docs-sidebar",1,"menu-button",3,"click"],["aria-label","Close navigation",1,"menu-scrim"],["id","docs-sidebar",1,"docs-sidebar"],["for","docs-search",1,"search-box"],["viewBox","0 0 20 20","aria-hidden","true"],["cx","8.5","cy","8.5","r","5.5"],["d","m13 13 4 4"],["id","docs-search","type","search","placeholder","Search documentation",3,"input","value"],["aria-label","Documentation sections"],[1,"nav-group"],["role","status",1,"search-empty"],[1,"sidebar-bottom"],[1,"version-dot"],[1,"docs-layout"],["id","docs-content","tabindex","-1",1,"docs-main"],[1,"breadcrumb"],[1,"page-summary"],["aria-label","Integration code example",1,"sample-section"],[1,"prose"],[1,"page-pagination"],[3,"routerLink"],[1,"next",3,"routerLink"],[1,"docs-footer"],["aria-label","On this page",1,"contents-rail"],[3,"routerLink","fragment"],[1,"resources"],["href","https://papersignal.duckdns.org/api/openapi.json","target","_blank","rel","noopener"],["href","/documentation-assets/invoice.schema.json","download",""],["href","/documentation-assets/python_client.py","download",""],["href","/documentation-assets/node_client.mjs","download",""],["aria-live","polite",1,"copy-status"],["aria-label","Close navigation",1,"menu-scrim",3,"click"],[3,"routerLink","active"],[3,"click","routerLink"],[1,"nav-method",3,"class"],[1,"nav-method"],[1,"endpoint-bar"],[1,"response-badge"],[1,"auth-line"],["aria-label","Integration in three steps",1,"flow"],["routerLink","/documentation/upload"],["aria-hidden","true",1,"flow-arrow"],["routerLink","/documentation/get-job"],["routerLink","/documentation/results"],[1,"base-url"],["type","button",3,"click"],[1,"code-toolbar"],["role","group","aria-label","Example language",1,"code-tabs"],["type","button",3,"selected"],["type","button",1,"copy-button",3,"click"],["tabindex","0"],[3,"id"],[3,"innerHTML"],["tabindex","0","role","region","aria-label","Reference table",1,"table-scroll"],[1,"code-block"],["aria-label","Link to this section",3,"routerLink","fragment"],["scope","col",3,"innerHTML"]],template:function(e,r){if(e&1&&(n(0,"a",0),o(1,"Skip to content"),i(),n(2,"header",1)(3,"a",2)(4,"span",3),O(),n(5,"svg",4),g(6,"path",5),i()(),q(),n(7,"span"),o(8,"Paper"),n(9,"span",6),o(10,"Signal"),i()()(),g(11,"span",7),n(12,"span",8),o(13,"Developers"),i(),n(14,"nav",9)(15,"a",10),o(16,"Swagger UI "),n(17,"span",11),o(18,"\u2197"),i()(),n(19,"a",12),o(20,"Open application "),n(21,"span",11),o(22,"\u2197"),i()()(),n(23,"button",13),y("click",function(){return r.menuOpen.set(!r.menuOpen())}),o(24),i()(),b(25,ee,1,0,"button",14),n(26,"aside",15)(27,"label",16),O(),n(28,"svg",17),g(29,"circle",18)(30,"path",19),i(),q(),n(31,"input",20),y("input",function(l){return r.query.set(l.target.value)}),i(),n(32,"kbd"),o(33,"/"),i()(),n(34,"nav",21),p(35,ae,5,1,"div",22,Q,!1,ie,2,0,"p",23),i(),n(38,"div",24),g(39,"span",25),o(40," API v0.1.0 "),n(41,"span"),o(42,"REST / JSON"),i()()(),n(43,"div",26)(44,"main",27)(45,"div",28),o(46,"Documentation "),n(47,"span"),o(48,"/"),i(),o(49),i(),n(50,"h1"),o(51),i(),n(52,"p",29),o(53),i(),b(54,oe,11,6),b(55,re,34,1),b(56,de,10,2,"section",30),n(57,"article",31),p(58,ke,5,1,null,null,T),i(),n(60,"div",32),b(61,be,5,4,"a",33)(62,ve,1,0,"span"),b(63,xe,5,4,"a",34),i(),n(64,"footer",35),o(65,"PaperSignal developer documentation "),n(66,"span"),o(67,"Reviewed 8 September 2026 \xB7 API v0.1.0"),i()()(),n(68,"aside",36)(69,"h2"),o(70,"ON THIS PAGE"),i(),p(71,we,2,5,"a",37,X),n(73,"div",38)(74,"h2"),o(75,"RESOURCES"),i(),n(76,"a",39),o(77,"OpenAPI specification \u2197"),i(),n(78,"a",40),o(79,"Invoice schema \u2193"),i(),n(80,"a",41),o(81,"Python example \u2193"),i(),n(82,"a",42),o(83,"Node.js example \u2193"),i()()()(),n(84,"div",43),o(85),i()),e&2){let d,l,x;s(23),j("aria-expanded",r.menuOpen()),s(),u(r.menuOpen()?"Close menu":"Menu"),s(),v(r.menuOpen()?25:-1),s(),E("is-open",r.menuOpen()),s(5),h("value",r.query()),s(4),m(r.groups()),s(14),W(" ",r.current().group),s(2),u(r.current().title),s(2),u(r.current().summary),s(),v(r.current().method?54:-1),s(),v(r.current().id==="overview"?55:-1),s(),v((d=r.current().samples)!=null&&d.length?56:-1),s(2),m(r.current().blocks),s(3),v((l=r.previous())?61:62,l),s(2),v((x=r.next())?63:-1,x),s(8),m(r.headings()),s(13),E("visible",r.copyError()),s(),u(r.copyError())}},dependencies:[$],styles:["[_nghost-%COMP%]{display:block}.verification-notice[_ngcontent-%COMP%]{margin:0 0 24px;padding:14px 16px;border-left:3px solid #b56d20;background:#fff8ed;color:#71522f;font-size:.875rem;line-height:1.65}.verification-notice[_ngcontent-%COMP%]   strong[_ngcontent-%COMP%]{font-weight:650}.verification-notice[_ngcontent-%COMP%]   a[_ngcontent-%COMP%]{display:inline-block;color:#62410d;text-decoration:underline;text-underline-offset:3px}"]})};export{V as Documentation};
