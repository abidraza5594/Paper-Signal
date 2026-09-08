# API test results

## Main finding
**The API accepts and manages jobs, but real PDF extraction did not succeed in this test run. Do not treat the service as ready for successful extraction yet.**

Test date: 8 September 2026. AWS test window: 12:02-12:04 India time (06:32-06:34 UTC). One later single-document retry also failed. Only artificial sample PDFs were used.

## Test summary
| Test set | Result |
|---|---|
| AWS live API checks | 54 passed, 4 failed. The four failures were real extraction jobs. |
| AWS single-document retry | Upload returned 202, then extraction failed. This was sent after the earlier jobs had finished. |
| Local API checks with real Mistral | 80 passed, 4 failed. The same four extraction cases failed. |
| Existing backend automated tests | All 44 passed. These include tests with controlled AI responses; they do not prove real AI success. |

The image-only PDF tested with ocr_mode=never failed as expected. That is a passed error-handling test, not an unexpected failure.

## Each API and its result
| API | AWS result | Local result |
|---|---|---|
| GET /api/health | Passed: 200 and configured limits returned. | Passed. |
| POST /api/jobs | File accepted with 202. Actual extraction failed. Invalid inputs were correctly rejected. | Same result with real AI. |
| POST /api/jobs/batch | Two valid files accepted and one invalid file rejected. Actual extraction failed for both valid files. | Same result with real AI. |
| GET /api/jobs/{job_id} | Passed: returned the job and its failed status. A successful live result could not be verified. | Passed for reading states and errors. |
| GET /api/batches/{batch_id} | Passed: returned the test batch's jobs. | Passed, including other-key rejection. |
| GET /api/jobs/batch?ids=... | Passed: ID lookup, duplicate removal and missing-ID behavior. | Passed, including other-key filtering. |
| GET /api/jobs?limit=20 | Passed: test jobs were present in the recent list. | Passed, including key ownership. |
| DELETE /api/jobs/{job_id} | Passed: finished test jobs deleted; processing deletion returned 409; later reads returned 404. | Passed. |
| GET /api/usage | Passed: key accepted, allowance reported and accepted documents counted. | Passed, including quota and rate-limit errors. |
| POST /api/admin/keys | Client key correctly rejected with 401. Successful creation not tested on AWS without an admin token. | Passed: isolated test keys created. |
| GET /api/admin/keys | Client key correctly rejected with 401. Authorized listing not tested on AWS. | Passed: key metadata listed without raw keys. |
| DELETE /api/admin/keys/{key_id} | Client key correctly rejected with 401. Authorized revocation not tested on AWS. | Passed: only test keys revoked; repeated revocation returned 409. |

## Extraction cases
| Document and mode | Expected | AWS result |
|---|---|---|
| Text PDF, never | Extract invoice number, amount and currency. | Failed at Structured extraction with AI_EXTRACTION_ERROR. |
| Text PDF in a batch, auto | Extract the same known values. | Failed at Structured extraction with AI_EXTRACTION_ERROR. |
| Scanned PDF in a batch, auto | Read the scan and extract the known values. | Failed at Structured extraction with AI_EXTRACTION_ERROR. |
| Scanned PDF, always | Use OCR and extract the known values. | Failed at Structured extraction with AI_EXTRACTION_ERROR. |
| Scanned PDF, never | Fail because there is no embedded text. | Failed as expected with “No readable text was found in the PDF.” |

The scan jobs reported one OCR page and reached the structured extraction stage. This does not establish OCR accuracy; no completed business result was returned.

## Error observed
AWS job responses reported:
```text
failure_code: AI_EXTRACTION_ERROR
failure_stage: Structured extraction
error: Mistral structured extraction failed with all configured Mistral API keys (SDKError).
```
The local test's real provider response was:
```text
HTTP 429
message: Rate limit exceeded
type: rate_limited
code: 1300
```
This confirms a provider rate-limit error for the local configured Mistral account. AWS returned the same application-level failure, but its provider response/server logs were not available, so the exact AWS upstream cause is not confirmed.

## What to check next
The service owner should check the Mistral model's request/token limits and the account/workspace usage limits. These are separate from the PaperSignal client key's requests-per-minute setting. Mistral explains them in its [usage and limits guide](https://docs.mistral.ai/admin/billing-usage/usage-limits).

The application already retries some provider errors. A single AWS document still failed after the earlier batch finished, so simply sending fewer test files did not resolve it. Check the AWS server's provider error before changing settings. Then repeat one text-PDF test and one scan test and confirm both return status completed with correct data.

## Other checks that passed
Missing/wrong credentials, Bearer authentication, header priority, invalid JSON/schema, missing schema, invalid OCR mode, empty/non-PDF/protected files, page-count limits, batch file-count limits, all-rejected batches, missing IDs, more than 50 IDs, unknown records, usage counting and test-job deletion were checked on AWS.

Local tests additionally checked separate-key ownership, new-key issuance, rate-limit 429 with Retry-After, monthly-quota 402, key revocation and rejection after revocation. These cases used isolated keys and local data.

## Test cleanup
All six AWS sample jobs were deleted: five from the main run and one later single-document retry. Only jobs created by these tests were deleted. The supplied client key was not changed or revoked. Accepted documents still count toward usage after deletion.

All local test jobs were deleted and the three locally created test keys were revoked. No customer document was used.

## Not yet verified
- Successful real extraction and extracted-value accuracy.
- Authorized AWS admin operations and isolation between two valid AWS client keys.
- Exhausting the supplied live key's quota or deliberately filling its request limit.
- Large-upload proxy limits, load capacity and restart recovery.
- Browser CORS against another deployed application and provider retention terms.

Passing upload/status tests does not remove these gaps. The next release check must include a completed, correct extraction result.
