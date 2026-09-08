# Developer documentation website

The primary deliverable is the Angular documentation website at `/documentation`, not a Markdown viewer. It provides 22 topic/endpoint pages in simple English, searchable navigation, direct links, code-language choices, copy buttons, responsive navigation and downloadable clients. `/api/docs` remains the separate Swagger explorer.

## Sources

- frontend/src/app/documentation: Angular page, navigation, typed content and tests.
- frontend/src/documentation.scss: route-scoped documentation theme.
- API_INTEGRATION.md: reviewed reference material used by the content generator.
- SERVICE_ASSESSMENT.md: manager assessment and verification scope.
- generate_website_content.py: compiles content and copies client downloads into frontend/public/documentation-assets.
- website_plain_english.py: current user-facing page copy; replaces the earlier technical drafts during compilation.
- API_TEST_RESULTS.md: dated test report displayed on the website. The extraction warning reflects the failures observed in this report; update it only after successful real extraction is verified.
- examples/integration: runnable client sources and schema.

From the repository root, refresh content with `backend/.venv/Scripts/python.exe docs/generate_website_content.py`. Then run the frontend's normal build/test scripts. No new npm dependencies are required.

## Existing AWS application

The normal frontend production build includes `/documentation`, `/documentation/:page`, the existing extraction application at `/`, and a documentation link in its header. The existing Caddy SPA fallback supports refreshing documentation deep links.

Publish the built frontend/browser output using the existing frontend deployment process. Upload hashed assets and documentation-assets before switching index.html, and retain the previous release for rollback. Backend routes and AWS settings are unchanged by this documentation task.

On 8 September 2026, public HTTPS endpoints were reachable, but the deployment SSH connection to the documented server timed out. Therefore this task did not publish the changed frontend to the existing AWS domain. Do not describe the AWS /documentation path as live until that frontend deployment completes.

## Standalone preview distribution

The separate documentation entry point contains only the documentation application, without the PDF upload console. It links users back to the existing AWS application/API. Build it from frontend with:

```powershell
npm exec -- ng build --browser src/documentation-main.ts --index src/documentation-index.html --output-path dist/documentation
```

Its HTML output is named documentation-index.html; deploy it as index.html for static hosting. The isolated documentation-site directory holds the static distribution and its Sites manifest/repository. Its SPA fallback is configured explicitly. It does not include provider credentials or customer documents.

## Verification

- Backend: 44 existing tests passed with isolated data.
- Frontend: 39 tests passed, including 4 documentation navigation/context/example checks.
- Both production builds passed: existing application and documentation-only entry point.
- All 22 page IDs, 12 endpoint operations, local links and download assets were checked.
- Python and Node client multipart, success, rate-limit retry, terminal-failure and 401 behavior were checked with mocked HTTP transports.
- Public AWS health/Swagger/OpenAPI returned 200; usage without a key returned 401.

The follow-up tested real AI and live AWS APIs: 80 local checks passed with 4 extraction failures; 54 AWS checks passed with 4 extraction failures. A later isolated AWS extraction also failed. All test jobs were cleaned up. See API_TEST_RESULTS.md for the exact scope and remaining gaps. Browser screenshot/visual QA was not performed in this task.
