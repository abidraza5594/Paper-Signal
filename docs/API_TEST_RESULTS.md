# API test results

## Main finding
**Extraction works. Every API was checked on the live AWS service and a real PDF was read end to end.**

Last checked: 8 September 2026. A one-page invoice PDF returned
`{"invoiceNumber":"INV-2026-777","total":4500}` in about two seconds.

## What the earlier failures were
An earlier run on the same day recorded failed extractions. The cause was **not** the
service: the AI provider account had a request limit of zero, so every AI call was
refused with HTTP 429. The provider's own response headers confirmed it:

```
x-ratelimit-limit-req-minute: 0
x-ratelimit-remaining-req-minute: 0
```

Three separate keys from that account behaved identically, which showed the limit was
applied to the account, not to any one key. A key from a working account fixed it
immediately, with no code change.

Two improvements came out of that investigation:

- Failures now report **why** they happened. A rate limit returns `AI_RATE_LIMITED`
  with "retry in a few minutes" instead of an unhelpful `SDKError`. Bad credentials
  return `AI_AUTH_FAILED`, and provider outages return `AI_PROVIDER_UNAVAILABLE`.
- Rate-limited and transient calls are retried with exponential backoff before the
  document is marked failed.

## Test summary
| Test set | Result |
|---|---|
| Live AWS API checks | All endpoints pass, including authentication, isolation, rate limits, quota and deletion. |
| Live extraction on AWS | Passes. A real PDF returned the requested fields. |
| Backend automated tests | 48 pass. |
| Frontend automated tests | 35 pass. |

The image-only PDF tested with `ocr_mode=never` fails by design. That is a passed
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
| Scanned PDF, never | Fail because there is no embedded text. | Failed as expected with “No readable text was found in the PDF.” |

The scan jobs reported one OCR page and completed. This does not establish OCR accuracy across document types; check your own documents before relying on it.

## What the error looked like before the fix

While the provider account was blocked, every document failed like this:

```text
failure_code: AI_EXTRACTION_ERROR
failure_stage: Structured extraction
error: Mistral structured extraction failed with all configured Mistral API keys (SDKError).
```

That message did not say whether to retry, fix credentials or fix the document. Failures
are now classified, so the same situation reports:

```text
failure_code: AI_RATE_LIMITED
error: The AI provider is rate limiting this service. The document was not processed.
       Retry in a few minutes.
```

## What to check next

- Run your own documents through the service. The tests above used small synthetic PDFs;
  accuracy on your real layouts is the thing worth measuring.
- Watch the provider account's limits. A limit of zero blocks every request regardless of
  which key is used, so check the account rather than issuing new keys.
- Confirm OCR quality on scans that matter to you, using `ocr_mode=auto`.
- Load and restart-recovery behaviour, large proxied uploads, and the provider's data
  retention terms are still unverified.
