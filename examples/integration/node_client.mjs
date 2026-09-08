// Node.js 22+, native Fetch/FormData. This example buffers the PDF in memory.
// Only polling requests are retried; uploads are sent exactly once.
import { readFile } from 'node:fs/promises';
import { pathToFileURL } from 'node:url';

const sleep = ms => new Promise(resolve => setTimeout(resolve, ms));

export async function upload(base, key, pdfPath, schema, ocrMode = 'auto') {
  const form = new FormData();
  form.append('file', new Blob([await readFile(pdfPath)], { type: 'application/pdf' }), 'document.pdf');
  form.append('output_template', JSON.stringify(schema));
  form.append('ocr_mode', ocrMode);
  const response = await fetch(`${base}/api/jobs`, {
    method: 'POST', headers: { 'X-API-Key': key }, body: form,
    signal: AbortSignal.timeout(120_000),
  });
  if (!response.ok) throw new Error(`Upload HTTP ${response.status}. Check the integration guide before retrying.`);
  return response.json();
}

export async function poll(base, key, jobId, maxWaitMs = 600_000, intervalMs = 3_000) {
  const deadline = Date.now() + maxWaitMs;
  let failures = 0;
  while (Date.now() < deadline) {
    let response;
    try {
      response = await fetch(`${base}/api/jobs/${encodeURIComponent(jobId)}`, {
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
      const delay = raw && /^\d+$/.test(raw) ? Math.max(intervalMs, Number(raw) * 1000) : fallback;
      await response.body?.cancel();
      await sleep(Math.max(0, Math.min(delay, deadline - Date.now())));
      continue;
    }
    if (!response.ok) throw new Error(`Polling HTTP ${response.status}; job ${jobId}.`);
    const job = await response.json();
    failures = 0;
    if (job.status === 'completed') return job.result;
    if (job.status === 'failed') throw new Error(`Job ${jobId} failed: ${job.failure_code} at ${job.failure_stage}. Retrieve job details.`);
    await sleep(Math.max(0, Math.min(intervalMs, deadline - Date.now())));
  }
  throw new Error(`Polling deadline reached. Job ${jobId} may still be running; keep the ID and check later.`);
}

async function main() {
  const pdfPath = process.argv[2];
  const key = process.env.PAPERSIGNAL_API_KEY?.trim();
  if (!pdfPath || !key) throw new Error('Set PAPERSIGNAL_API_KEY, then run: node node_client.mjs document.pdf [schema.json]');
  const base = (process.env.PAPERSIGNAL_BASE_URL || 'https://papersignal.duckdns.org').replace(/\/+$/, '');
  const schema = JSON.parse(await readFile(process.argv[3] || new URL('./invoice.schema.json', import.meta.url), 'utf8'));
  const job = await upload(base, key, pdfPath, schema);
  console.error(`Accepted job: ${job.id} (save this ID)`);
  console.log(JSON.stringify(await poll(base, key, job.id), null, 2));
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  main().catch(error => { console.error(error.message); process.exitCode = 1; });
}
