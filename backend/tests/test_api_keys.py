import fitz
import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr

from app import main
from app.api_keys import ApiKeyStore, RateLimiter, RateLimitExceeded, hash_key


OUTPUT_SCHEMA = '{"type":"object","properties":{"total":{"type":"string"}}}'
ADMIN = {"X-Admin-Token": "admin-secret"}


def pdf_bytes() -> bytes:
    document = fitz.open()
    page = document.new_page()
    page.insert_text((72, 72), "Invoice total INR 42")
    content = document.tobytes()
    document.close()
    return content


@pytest.fixture
def service(tmp_path, monkeypatch):
    """A fresh key store and job database per test, with auth switched on."""
    store = ApiKeyStore(tmp_path / "keys.sqlite3")
    store.initialize()
    monkeypatch.setattr(main, "api_keys", store)
    monkeypatch.setattr(main, "rate_limiter", RateLimiter())
    monkeypatch.setattr(main.settings, "require_api_key", True)
    monkeypatch.setattr(main.settings, "admin_token", SecretStr("admin-secret"))
    monkeypatch.setattr(main.settings, "mistral_api_key", SecretStr("test-key"))
    monkeypatch.setattr(main.runner, "submit", lambda job_id: None)
    return store


def _cleanup(payload_jobs):
    for job in payload_jobs:
        stored = main.database.get(job["id"])
        if stored:
            main.storage.delete(stored.file_path)
            main.database.delete(job["id"])


def test_keys_are_stored_hashed_and_returned_once(service):
    record, raw_key = service.create("acme corp", 60, 100)

    assert raw_key.startswith("ps_live_")
    assert record.key_prefix.endswith("...")
    assert raw_key not in record.key_prefix

    with service._connect() as connection:
        row = connection.execute(
            "SELECT key_hash FROM api_keys WHERE id = ?", (record.id,)
        ).fetchone()
    assert row["key_hash"] == hash_key(raw_key)
    assert raw_key not in row["key_hash"]
    assert service.find_by_raw_key(raw_key).id == record.id
    assert service.find_by_raw_key("ps_live_wrong") is None


def test_requests_without_a_key_are_rejected_when_auth_is_on(service):
    with TestClient(main.app) as client:
        assert client.get("/api/v1/account").status_code == 401
        assert client.get("/api/v1/account", headers={"X-API-Key": "ps_live_nope"}).status_code == 401
        # health stays public so a client can discover the service before it has a key
        assert client.get("/api/health").status_code == 200


def test_admin_can_issue_a_key_over_http(service):
    """Creating a key is the only key operation exposed over HTTP.

    Listing and revoking are deliberately server-side only (manage_keys.py), so a
    leaked admin token cannot enumerate or disable every client's access.
    """
    with TestClient(main.app) as client:
        assert client.post("/api/v1/keys", json={"name": "acme"}).status_code == 401

        created = client.post(
            "/api/v1/keys",
            json={"name": "acme", "rate_limit_per_minute": 5, "monthly_document_quota": 10},
            headers=ADMIN,
        )
        assert created.status_code == 201
        body = created.json()
        raw_key = body["key"]
        assert body["api_key"]["name"] == "acme"
        assert body["api_key"]["rate_limit_per_minute"] == 5

        assert client.get("/api/v1/account", headers={"X-API-Key": raw_key}).status_code == 200

    # revocation still works, through the store the CLI uses
    assert service.revoke(body["api_key"]["id"]) is True
    with TestClient(main.app) as client:
        assert client.get("/api/v1/account", headers={"X-API-Key": raw_key}).status_code == 401


def test_removed_endpoints_are_gone(service):
    """The old surface was 12 endpoints; these were dropped deliberately."""
    _, raw_key = service.create("probe", 60, 100)
    headers = {"X-API-Key": raw_key}
    with TestClient(main.app) as client:
        for method, path in [
            ("post", "/api/jobs"),
            ("get", "/api/jobs"),
            ("get", "/api/jobs/some-id"),
            ("get", "/api/jobs/batch"),
            ("get", "/api/usage"),
            ("get", "/api/batches/some-id"),
            ("get", "/api/admin/keys"),
        ]:
            response = getattr(client, method)(path, headers={**headers, **ADMIN})
            assert response.status_code == 404, f"{method.upper()} {path} still exists"


def test_bearer_header_is_accepted_too(service):
    _, raw_key = service.create("bearer client", 60, 100)
    with TestClient(main.app) as client:
        assert client.get(
            "/api/v1/account", headers={"Authorization": f"Bearer {raw_key}"}
        ).status_code == 200


def test_each_client_only_sees_its_own_jobs(service):
    _, key_a = service.create("client a", 60, 100)
    _, key_b = service.create("client b", 60, 100)

    with TestClient(main.app) as client:
        created = client.post(
            "/api/v1/extractions",
            files=[("files", ("a.pdf", pdf_bytes(), "application/pdf"))],
            data={"output_template": OUTPUT_SCHEMA, "ocr_mode": "auto"},
            headers={"X-API-Key": key_a},
        )
        assert created.status_code == 202
        payload = created.json()
        job_id = payload["jobs"][0]["id"]
        extraction_id = payload["extraction_id"]

        owner = client.get(f"/api/v1/extractions/{extraction_id}", headers={"X-API-Key": key_a})
        assert owner.status_code == 200
        assert owner.json()[0]["id"] == job_id

        # the other client cannot read or delete it, and is not told it exists
        assert client.get(
            f"/api/v1/extractions/{extraction_id}", headers={"X-API-Key": key_b}
        ).status_code == 404
        assert client.delete(
            f"/api/v1/extractions/{extraction_id}", headers={"X-API-Key": key_b}
        ).status_code == 404

        _cleanup(payload["jobs"])


def test_rate_limit_returns_429_with_retry_after(service):
    _, raw_key = service.create("busy client", 2, 100)
    with TestClient(main.app) as client:
        assert client.get("/api/v1/account", headers={"X-API-Key": raw_key}).status_code == 200
        assert client.get("/api/v1/account", headers={"X-API-Key": raw_key}).status_code == 200
        blocked = client.get("/api/v1/account", headers={"X-API-Key": raw_key})

    assert blocked.status_code == 429
    assert int(blocked.headers["Retry-After"]) >= 1
    assert "2 requests per minute" in blocked.json()["detail"]


def test_monthly_quota_blocks_further_documents(service):
    record, raw_key = service.create("small plan", 60, 1)
    service.record_documents(record.id, 1)

    with TestClient(main.app) as client:
        response = client.post(
            "/api/v1/extractions",
            files=[("files", ("a.pdf", pdf_bytes(), "application/pdf"))],
            data={"output_template": OUTPUT_SCHEMA, "ocr_mode": "auto"},
            headers={"X-API-Key": raw_key},
        )

    assert response.status_code == 402
    assert "Monthly quota" in response.json()["detail"]


def test_usage_endpoint_reports_remaining_documents(service):
    record, raw_key = service.create("reporting client", 30, 10)
    service.record_documents(record.id, 4, pages=12)

    with TestClient(main.app) as client:
        usage = client.get("/api/v1/account", headers={"X-API-Key": raw_key}).json()

    assert usage["documents_this_month"] == 4
    assert usage["documents_remaining"] == 6
    assert usage["rate_limit_per_minute"] == 30
    assert usage["api_key"]["key_prefix"].startswith("ps_live_")


def test_submitting_documents_counts_against_the_quota(service):
    record, raw_key = service.create("counting client", 60, 100)

    with TestClient(main.app) as client:
        created = client.post(
            "/api/v1/extractions",
            files=[
                ("files", ("a.pdf", pdf_bytes(), "application/pdf")),
                ("files", ("b.pdf", pdf_bytes(), "application/pdf")),
                ("files", ("broken.pdf", b"not-a-pdf", "application/pdf")),
            ],
            data={"output_template": OUTPUT_SCHEMA, "ocr_mode": "auto"},
            headers={"X-API-Key": raw_key},
        )
        payload = created.json()

    # only the two accepted documents are billed, not the rejected one
    assert payload["accepted_count"] == 2
    assert service.documents_used(record.id) == 2
    _cleanup(payload["jobs"])


def test_local_mode_without_auth_still_works(service, monkeypatch):
    monkeypatch.setattr(main.settings, "require_api_key", False)
    with TestClient(main.app) as client:
        assert client.get("/api/health").status_code == 200
        # account still needs a key: it reports a specific key's usage
        assert client.get("/api/v1/account").status_code == 401


def test_rate_limiter_window_is_per_key():
    limiter = RateLimiter()
    limiter.check("key-a", 1)
    limiter.check("key-b", 1)
    with pytest.raises(RateLimitExceeded) as exc:
        limiter.check("key-a", 1)
    assert exc.value.retry_after_seconds >= 1
    limiter.reset("key-a")
    limiter.check("key-a", 1)
