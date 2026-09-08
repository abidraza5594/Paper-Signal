"""Python 3.11+ single-PDF integration example; standard library only.

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
        parts.append((f"--{boundary}\r\nContent-Disposition: form-data; name=\"{name}\"\r\n\r\n"
                      f"{value}\r\n").encode())
    # Constant upload filename avoids multipart-header injection from local paths.
    parts.append((f"--{boundary}\r\nContent-Disposition: form-data; name=\"files\"; "
                  "filename=\"document.pdf\"\r\nContent-Type: application/pdf\r\n\r\n").encode())
    parts.extend((pdf.read_bytes(), f"\r\n--{boundary}--\r\n".encode()))
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
