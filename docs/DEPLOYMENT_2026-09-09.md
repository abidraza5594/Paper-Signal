# AWS release — 9 September 2026

**Current release:** the later Gemini migration described below supersedes the
initial Mistral release in the first sections.

Target: existing `papersignal` App Runner service in `ap-south-1`, serving
https://ydb2zmspyn.ap-south-1.awsapprunner.com.

## Release identity

- Application commit: `4664096e0057c01e46786834a1a6bba3d6791035`.
- Frontend rebuilt from that source; entry bundle: `main-U2JEVDTU.js`.
- ECR release tag: `papersignal-api:release-4664096-20260909`.
- Image digest: `sha256:6b5b16ba06287ff753c496fd81c3cad1bb723cbb9fba5ab479e2150c8f582ed8`.
- App Runner operation: `94fbfa67422a46d19210bdd396266d83`.
- Existing service configuration, environment variables, IAM roles, S3 bucket and DynamoDB tables were retained.

## Checks before deployment

- 147 backend tests passed.
- 36 frontend tests passed; production frontend build passed.
- Linux/amd64 container built successfully, with a single image manifest.
- Local container became healthy and its extraction modules imported successfully.
- Default independent verification model is `mistral-large-2512`.
- Local evaluation artifacts are excluded from the Docker build context.

## Rollback

The previous image is preserved in ECR under
`papersignal-api:rollback-20260909-before-4664096`, digest
`sha256:fd91516340353812908a81ebeb499c5157f13471fd876c7bdc6c9bece84921be`.
To roll back, restore that manifest to the service's `latest` tag and start an App Runner deployment.
The previous local frontend build is also preserved under the ignored
`backend/live-results/deploy-20260909/web-before/` directory.

## Verification status

App Runner reported **SUCCEEDED**. Post-deployment checks passed:

- Public health returned HTTP 200.
- The live index matched the rebuilt frontend byte for byte.
- Documentation root/deep link, Swagger and OpenAPI returned HTTP 200.
- Account access without a key returned HTTP 401.
- A temporary test credential submitted a synthetic PDF through the public API.
- The live extraction completed with the exact three expected facts and `null` for an absent fax number; strict schema validation passed.
- The result reported `mistral-large-2512` as the independent verifier, with debug audit data absent from the public response.
- The test extraction and uploaded file were removed through the API (HTTP 204), and the temporary credential was revoked.

This deployment smoke test verifies the released end-to-end path, not arbitrary-document accuracy. The broader extraction evaluation and known limitations remain in [EXTRACTION_VALIDATION.md](EXTRACTION_VALIDATION.md).

Local deployment metadata and the synthetic smoke-test report are retained under
`backend/live-results/deploy-20260909/`, outside version control. No credentials are included in these reports.

## Gemini follow-up release

- Status: **SUCCEEDED**; App Runner operation `f4340a77c2d54ab887f1d543bca2b5e7`.
- Configured image: `397332850029.dkr.ecr.ap-south-1.amazonaws.com/papersignal-api:release-gemini-20260909`.
- Digest: `sha256:633ac2a29894dc44db5f611dad3c92b5d00a3a0d5ba1a1fb238d3cf5cae09f53`.
- Source: commit `4664096` plus the current Gemini provider working-tree changes.
- Provider: Gemini; extraction, vision transcription and verification model: `gemini-3.5-flash`.
- Backend key is configured in the service environment, not embedded in code or the frontend.
- One worker per instance and a 15-second minimum request-start interval per credential/process.
- Existing storage, database, application access keys, service URL and IAM roles retained.
- Verification: 158 backend tests passed; native and scanned live fixtures each matched 8/8 expected facts.
- Production smoke: live frontend/health/docs/auth checks passed; the synthetic PDF returned all three expected facts and null for missing fax; result confirmed Gemini and strict schema validity. Test extraction removed (HTTP 204) and temporary credential revoked.
- Local metadata and smoke report: `backend/live-results/deploy-gemini-20260909/`.

The previous image remains available as `release-4664096-20260909`. Returning to
Mistral requires restoring provider configuration and valid Mistral credentials;
the user deleted the previous provider key. The service now uses a versioned image
tag: a future release must update `ImageIdentifier` to its new tag while preserving
the existing source configuration/environment. `start-deployment` alone refreshes
the currently configured tag and does not switch it to `latest`.

See [Gemini configuration and evaluation scope](GEMINI_PROVIDER.md). The full
41-page brochure evaluation has not been repeated with Gemini in this migration.
