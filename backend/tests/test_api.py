import fitz
from fastapi.testclient import TestClient
from pydantic import SecretStr

from app import main


OUTPUT_SCHEMA = '{"type":"object","properties":{"total":{"type":"string"}}}'


def pdf_bytes() -> bytes:
    document = fitz.open()
    page = document.new_page()
    page.insert_text((72, 72), "Invoice number INV-100 and total INR 42")
    content = document.tobytes()
    document.close()
    return content


def multipage_pdf_bytes(page_count: int) -> bytes:
    document = fitz.open()
    for _ in range(page_count):
        document.new_page()
    content = document.tobytes()
    document.close()
    return content


def test_health_reports_upload_limit():
    with TestClient(main.app) as client:
        response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json()["max_upload_mb"] == 200
    assert response.json()["max_pdf_pages"] == 40
    assert response.json()["max_batch_files"] == 10
    assert response.json()["max_batch_total_mb"] == 500


def test_rejects_pdf_over_page_limit_before_job_creation(monkeypatch):
    monkeypatch.setattr(main.settings, "mistral_api_key", SecretStr("test-key"))
    with TestClient(main.app) as client:
        response = client.post(
            "/api/v1/extractions",
            files=[("files", ("too-long.pdf", multipage_pdf_bytes(41), "application/pdf"))],
            data={"output_template": OUTPUT_SCHEMA, "ocr_mode": "auto"},
        )

    # An oversized PDF is rejected per file, before any AI work starts.
    assert response.status_code == 202
    payload = response.json()
    assert payload["accepted_count"] == 0
    assert payload["rejected"][0]["error"] == (
        "PDF rejected: 41 pages detected. Maximum allowed is 40 pages."
    )


def test_rejects_invalid_output_json(monkeypatch):
    monkeypatch.setattr(main.settings, "mistral_api_key", SecretStr("test-key"))
    with TestClient(main.app) as client:
        response = client.post(
            "/api/v1/extractions",
            files=[("files", ("invoice.pdf", pdf_bytes(), "application/pdf"))],
            data={"output_template": "{not-json}"},
        )

    assert response.status_code == 422
    assert "Invalid JSON" in response.json()["detail"]


def test_rejects_free_text_instead_of_starting_extraction(monkeypatch):
    submitted: list[str] = []
    monkeypatch.setattr(main.settings, "mistral_api_key", SecretStr("test-key"))
    monkeypatch.setattr(main.runner, "submit", submitted.append)

    with TestClient(main.app) as client:
        response = client.post(
            "/api/v1/extractions",
            files=[("files", ("invoice.pdf", pdf_bytes(), "application/pdf"))],
            data={"output_template": "lorem"},
        )

    assert response.status_code == 422
    assert "Invalid JSON" in response.json()["detail"]
    assert submitted == []


def test_rejects_example_json_object(monkeypatch):
    monkeypatch.setattr(main.settings, "mistral_api_key", SecretStr("test-key"))

    with TestClient(main.app) as client:
        response = client.post(
            "/api/v1/extractions",
            files=[("files", ("invoice.pdf", pdf_bytes(), "application/pdf"))],
            data={"output_template": '{"total":"string"}'},
        )

    assert response.status_code == 422
    assert "JSON Schema" in response.json()["detail"]


def test_submit_returns_202_without_waiting_for_processing(monkeypatch):
    submitted: list[str] = []
    monkeypatch.setattr(main.settings, "mistral_api_key", SecretStr("test-key"))
    monkeypatch.setattr(main.runner, "submit", submitted.append)

    with TestClient(main.app) as client:
        response = client.post(
            "/api/v1/extractions",
            files=[("files", ("invoice.pdf", pdf_bytes(), "application/pdf"))],
            data={"output_template": OUTPUT_SCHEMA, "ocr_mode": "auto"},
        )

    assert response.status_code == 202
    payload = response.json()
    assert payload["extraction_id"]
    job = payload["jobs"][0]
    assert job["status"] == "queued"
    assert job["file_name"] == "invoice.pdf"
    assert job["schema_mode"] == "json_schema"
    assert job["extraction_id"] == payload["extraction_id"]
    assert submitted == [job["id"]]

    stored = main.database.get(job["id"])
    assert stored is not None
    main.storage.delete(stored.file_path)
    main.database.delete(job["id"])


def test_batch_accepts_multiple_pdfs_and_reports_invalid_files(monkeypatch):
    submitted: list[str] = []
    monkeypatch.setattr(main.settings, "mistral_api_key", SecretStr("test-key"))
    monkeypatch.setattr(main.runner, "submit", submitted.append)

    with TestClient(main.app) as client:
        response = client.post(
            "/api/v1/extractions",
            files=[
                ("files", ("one.pdf", pdf_bytes(), "application/pdf")),
                ("files", ("broken.pdf", b"not-a-pdf", "application/pdf")),
                ("files", ("two.pdf", pdf_bytes(), "application/pdf")),
            ],
            data={"output_template": OUTPUT_SCHEMA, "ocr_mode": "auto"},
        )

    assert response.status_code == 202
    payload = response.json()
    assert payload["accepted_count"] == 2
    assert payload["rejected_count"] == 1
    assert [job["file_name"] for job in payload["jobs"]] == ["one.pdf", "two.pdf"]
    assert payload["rejected"][0]["file_name"] == "broken.pdf"
    assert "not a valid PDF" in payload["rejected"][0]["error"]
    assert submitted == [job["id"] for job in payload["jobs"]]

    for job in payload["jobs"]:
        stored = main.database.get(job["id"])
        assert stored is not None
        main.storage.delete(stored.file_path)
        main.database.delete(job["id"])


def test_documents_share_an_extraction_id_and_reload_together(monkeypatch):
    monkeypatch.setattr(main.settings, "mistral_api_key", SecretStr("test-key"))
    monkeypatch.setattr(main.runner, "submit", lambda job_id: None)

    with TestClient(main.app) as client:
        response = client.post(
            "/api/v1/extractions",
            files=[
                ("files", ("one.pdf", pdf_bytes(), "application/pdf")),
                ("files", ("two.pdf", pdf_bytes(), "application/pdf")),
            ],
            data={"output_template": OUTPUT_SCHEMA, "ocr_mode": "auto"},
        )
        payload = response.json()
        extraction_id = payload["extraction_id"]

        assert extraction_id
        assert {job["extraction_id"] for job in payload["jobs"]} == {extraction_id}

        reloaded = client.get(f"/api/v1/extractions/{extraction_id}")
        assert reloaded.status_code == 200
        assert [job["file_name"] for job in reloaded.json()] == ["one.pdf", "two.pdf"]

        assert client.get("/api/v1/extractions/does-not-exist").status_code == 404

    for job in payload["jobs"]:
        stored = main.database.get(job["id"])
        assert stored is not None
        main.storage.delete(stored.file_path)
        main.database.delete(job["id"])


def test_batch_rejects_more_than_configured_file_limit(monkeypatch):
    monkeypatch.setattr(main.settings, "mistral_api_key", SecretStr("test-key"))
    monkeypatch.setattr(main.settings, "max_batch_files", 1)

    with TestClient(main.app) as client:
        response = client.post(
            "/api/v1/extractions",
            files=[
                ("files", ("one.pdf", pdf_bytes(), "application/pdf")),
                ("files", ("two.pdf", pdf_bytes(), "application/pdf")),
            ],
            data={"output_template": OUTPUT_SCHEMA},
        )

    assert response.status_code == 422
    assert "at most 1 PDFs" in response.json()["detail"]
