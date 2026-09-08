# Run a PaperSignal integration example

The clients submit one PDF and poll until completed/failed or a ten-minute deadline. They output the completed result object; use its `data` property for business values. They print the accepted job ID to stderr immediately. Your actual application should persist that ID with its business record and user's identity.

Both examples use built-in libraries only. They buffer the PDF in memory, so use small documents for these examples and a streaming multipart implementation for large uploads. Neither deletes jobs automatically nor retries uploads. Running a client against AWS uploads the PDF to the service, consumes document quota and can incur provider processing usage.

## Configure

The service operator must issue your application's client key. Set `PAPERSIGNAL_API_KEY` privately in your backend environment; do not commit or share it. Optional `PAPERSIGNAL_BASE_URL` defaults to `https://papersignal.duckdns.org`. A local test server can use `http://localhost:8000`.

PowerShell environment syntax (replace the placeholder privately):

```powershell
$env:PAPERSIGNAL_API_KEY = '<YOUR_CLIENT_KEY>'
$env:PAPERSIGNAL_BASE_URL = 'https://papersignal.duckdns.org'
```

Run from this directory, with a PDF path you control:

```powershell
# Python 3.11+, no pip packages required
python python_client.py 'C:\Documents\invoice.pdf'
python python_client.py 'C:\Documents\invoice.pdf' --ocr-mode never --wait-seconds 900 --poll-seconds 5

# Node.js 22+, no npm packages required
node node_client.mjs 'C:\Documents\invoice.pdf'
```

Custom schema:

```powershell
python python_client.py 'C:\Documents\invoice.pdf' --schema custom.schema.json
node node_client.mjs 'C:\Documents\invoice.pdf' custom.schema.json
```

Edit the supplied invoice schema to match your required fields. Never set multipart Content-Type manually when using native FormData; it supplies the boundary. Native Node FormData needs a Blob/File for file uploads, not an fs.createReadStream value.

## Integrate into an application

Move the upload and poll operations into your backend/background worker; keep your own user request short. Persist the returned ID, verify the key's limits through `/api/v1/account`, and coordinate polling across callers. A single three-second polling stream uses roughly 20 requests/minute. For many jobs, use the batch or multi-ID polling API described in [the API guide](../../docs/API_INTEGRATION.md).

Validate returned values before saving or triggering business actions. A client timeout does not cancel the job. Upload timeouts/lost responses may leave accepted work; reconcile before retrying because there is no idempotency support. Non-2xx errors need handling, and successful HTTP polling can still report a failed job.

Verification for this handoff: clients exercised with mocked HTTP transports for success, rate-limit retry, terminal failure and HTTP authentication errors. This is not a live Mistral extraction test. See [assessment](../../docs/SERVICE_ASSESSMENT.md) for the full verification boundary.
