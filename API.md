# PaperSignal API documentation

The developer documentation website is available at `/documentation` in the frontend. It includes a quick start, all 12 API operations, authentication, schemas, error handling, operational considerations, and downloadable Python/Node.js clients.

The interactive API explorer remains at [Swagger UI](https://papersignal.duckdns.org/api/docs), with [OpenAPI JSON](https://papersignal.duckdns.org/api/openapi.json) for Postman imports.

Maintainer sources:

- [Reviewed API guide](docs/API_INTEGRATION.md)
- [Service integration assessment](docs/SERVICE_ASSESSMENT.md)
- [Client examples](examples/integration/README.md)

The website content is compiled by `docs/generate_website_content.py` into the Angular documentation module and public example downloads. After changing source documentation or clients, run the generator and rebuild the frontend.

Reviewed 8 September 2026. Live authenticated tests found that job APIs respond, but real extraction fails. See [the test report](docs/API_TEST_RESULTS.md) and the website's API test results page.
