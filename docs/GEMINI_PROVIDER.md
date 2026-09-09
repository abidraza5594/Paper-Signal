# Gemini provider

Set `AI_PROVIDER=gemini` and provide `GEMINI_API_KEY` on the backend only.
The selected default is `gemini-3.5-flash` for candidate extraction, visual
transcription and independent verification requests. Both text and verification
models can be overridden separately with `GEMINI_TEXT_MODEL` and
`GEMINI_VERIFICATION_MODEL`. The original Mistral provider remains available when
selected explicitly.

The adapter sends credentials in the request header, never in URLs. It uses the
same source evidence, schema rules, candidate checks and deterministic assembly
as the Mistral pipeline. Gemini's generation schema is only a transport subset;
the complete response schema and the user's unmodified schema are checked locally.
Scanned pages use Gemini visual transcription; no Mistral OCR call is made.

`GEMINI_MIN_REQUEST_INTERVAL_SECONDS=15` spaces request starts per credential
within one backend process. A server-directed retry delay also delays other
workers using that credential. This is not a distributed quota limiter: other
processes/instances and tools using the project share the provider's quota.
It does not guarantee that token or daily quotas cannot be exceeded. Authentication
and quota failures during transcription stop the job rather than triggering a
second series of OCR calls.

## Verification on 9 September 2026

- The supplied credential passed model discovery and a real image-to-JSON test.
- Gemini 3.8 Flash passed that small image test but returned HTTP 503 / high demand
  for the full candidate request. Gemini 2.5 Flash returned 404 on the tested endpoint.
- Gemini 3.5 Flash completed the actual pipeline: the generated native PDF and
  rasterized scanned PDF each returned all 8 expected facts, no wrong or missing
  facts, and null for the absent date. Both matched the independent expected JSON.
- The native candidate response was reused for its exact-request verification run;
  verification was a real Gemini call. The scanned run performed real visual
  transcription, candidate extraction and image-based verification.
- 158 offline backend tests passed, including provider selection, independent
  model routing, response/schema checks, rate-limit retry, authentication failure,
  incomplete responses and shared process pacing.

This is an integration evaluation, not proof of arbitrary-document accuracy. The
41-page brochure and three supplied schemas have not been fully re-benchmarked
with Gemini in this migration. The earlier brochure results in
[EXTRACTION_VALIDATION.md](EXTRACTION_VALIDATION.md) were obtained with Mistral.

Local evaluation artifacts are under `backend/live-results/gemini-native/` and
`backend/live-results/gemini-scan/`, excluded from git and Docker build context.
Use `verify_grounding.py --provider gemini --pdf ... --schema ... --output ...`
for subsequent controlled evaluations. Provider free-tier availability and quotas
must be checked in the provider account; changing a key does not reset a project's quota.

References: [Gemini API](https://ai.google.dev/api/generate-content),
[structured outputs](https://ai.google.dev/gemini-api/docs/structured-output),
[rate limits](https://ai.google.dev/gemini-api/docs/rate-limits).
