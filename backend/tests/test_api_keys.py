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
        assert client.get("/api/jobs").status_code == 401
        assert client.get("/api/jobs", headers={"X-API-Key": "ps_live_nope"}).status_code == 401


def test_admin_can_issue_list_and_revoke_keys(service):
    with TestClient(main.app) as client:
        assert client.post("/api/admin/keys", json={"name": "acme"}).status_code == 401

        created = client.post(
            "/api/admin/keys",
            json={"name": "acme", "rate_limit_per_minute": 5, "monthly_document_quota": 10},
            headers=ADMIN,
        )
        assert created.status_code == 201
        body = created.json()
        raw_key = body["key"]
        key_id = body["api_key"]["id"]
        assert body["api_key"]["name"] == "acme"

        listed = client.get("/api/admin/keys", headers=ADMIN).json()
        assert [item["id"] for item in listed] == [key_id]
        assert "key" not in listed[0]

        assert client.get("/api/jobs", headers={"X-API-Key": raw_key}).status_code == 200

        assert client.delete(f"/api/admin/keys/{key_id}", headers=ADMIN).status_code == 204
        assert client.delete(f"/api/admin/keys/{key_id}", headers=ADMIN).status_code == 409
        assert client.get("/api/jobs", headers={"X-API-Key": raw_key}).status_code == 401


def test_bearer_header_is_accepted_too(service):
    _, raw_key = service.create("bearer client", 60, 100)
    with TestClient(main.app) as client:
        assert client.get(
            "/api/jobs", headers={"Authorization": f"Bearer {raw_key}"}
        ).status_code == 200


def test_each_client_only_sees_its_own_jobs(service):
    _, key_a = service.create("client a", 60, 100)
    _, key_b = service.create("client b", 60, 100)

    with TestClient(main.app) as client:
        created = client.post(
            "/api/jobs/batch",
            files=[("files", ("a.pdf", pdf_bytes(), "application/pdf"))],
            data={"output_template": OUTPUT_SCHEMA, "ocr_mode": "auto"},
            headers={"X-API-Key": key_a},
        )
        assert created.status_code == 202
        payload = created.json()
        job_id = payload["jobs"][0]["id"]
        batch_id = payload["batch_id"]

        assert client.get("/api/jobs", headers={"X-API-Key": key_a}).json()[0]["id"] == job_id
        assert client.get(f"/api/jobs/{job_id}", headers={"X-API-Key": key_a}).status_code == 200

        # the other client cannot read, list, or delete it
        assert client.get("/api/jobs", headers={"X-API-Key": key_b}).json() == []
        assert client.get(f"/api/jobs/{job_id}", headers={"X-API-Key": key_b}).status_code == 404
        assert client.get(f"/api/batches/{batch_id}", headers={"X-API-Key": key_b}).status_code == 404
        assert client.get(
            "/api/jobs/batch", params={"ids": job_id}, headers={"X-API-Key": key_b}
        ).json() == []
        assert client.delete(f"/api/jobs/{job_id}", headers={"X-API-Key": key_b}).status_code == 404

        _cleanup(payload["jobs"])


def test_rate_limit_returns_429_with_retry_after(service):
    _, raw_key = service.create("busy client", 2, 100)
    with TestClient(main.app) as client:
        assert client.get("/api/jobs", headers={"X-API-Key": raw_key}).status_code == 200
        assert client.get("/api/jobs", headers={"X-API-Key": raw_key}).status_code == 200
        blocked = client.get("/api/jobs", headers={"X-API-Key": raw_key})

    assert blocked.status_code == 429
    assert int(blocked.headers["Retry-After"]) >= 1
    assert "2 requests per minute" in blocked.json()["detail"]


def test_monthly_quota_blocks_further_documents(service):
    record, raw_key = service.create("small plan", 60, 1)
    service.record_documents(record.id, 1)

    with TestClient(main.app) as client:
        response = client.post(
            "/api/jobs/batch",
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
        usage = client.get("/api/usage", headers={"X-API-Key": raw_key}).json()

    assert usage["documents_this_month"] == 4
    assert usage["documents_remaining"] == 6
    assert usage["rate_limit_per_minute"] == 30
    assert usage["api_key"]["key_prefix"].startswith("ps_live_")


def test_submitting_documents_counts_against_the_quota(service):
    record, raw_key = service.create("counting client", 60, 100)

    with TestClient(main.app) as client:
        created = client.post(
            "/api/jobs/batch",
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
        assert client.get("/api/jobs").status_code == 200
        assert client.get("/api/usage").status_code == 401


def test_rate_limiter_window_is_per_key():
    limiter = RateLimiter()
    limiter.check("key-a", 1)
    limiter.check("key-b", 1)
    with pytest.raises(RateLimitExceeded) as exc:
        limiter.check("key-a", 1)
    assert exc.value.retry_after_seconds >= 1
    limiter.reset("key-a")
    limiter.check("key-a", 1)
