import json

import httpx
import pytest

from app.config import Settings
from app.gemini_service import GeminiDocumentService, generation_schema
from app.mistral_service import AiExtractionError


def settings(**kwargs):
    return Settings(_env_file=None, ai_provider="gemini", gemini_api_key="test-gemini-key",
        gemini_min_request_interval_seconds=0, **kwargs)


def response(text, finish="STOP"):
    return {"candidates": [{"finishReason": finish, "content": {"parts": [{"text": text}]}}]}


def service(handler, **kwargs):
    return GeminiDocumentService(settings(**kwargs), client=httpx.Client(transport=httpx.MockTransport(handler)))


def test_gemini_configuration_does_not_require_mistral_key():
    s = settings()
    assert s.ai_configured
    assert s.text_model == s.verification_model == s.ocr_model == "gemini-3.5-flash"
    assert not Settings(_env_file=None, ai_provider="gemini", mistral_api_key="old").ai_configured


def test_vision_request_uses_header_and_image_and_strict_response():
    def handle(request):
        assert request.headers["x-goog-api-key"] == "test-gemini-key"
        assert "test-gemini-key" not in str(request.url)
        body = json.loads(request.content)
        assert body["contents"][0]["parts"][1]["inlineData"] == {"mimeType": "image/png", "data": "YWJj"}
        assert body["generationConfig"]["responseMimeType"] == "application/json"
        return httpx.Response(200, json=response('{"n":7}'))
    ai = service(handle)
    assert ai._generate("gemini-3.8-flash", "Read count", ["data:image/png;base64,YWJj"],
        {"type": "object", "properties": {"n": {"const": 7}}, "required": ["n"]}) == {"n": 7}


def test_full_local_schema_retains_array_enum_despite_generation_subset():
    schema = {"type": "object", "properties": {"path": {"type": "array", "items": {"type": "string"}, "enum": [["right"]]}}, "required": ["path"]}
    assert "enum" not in generation_schema(schema)["properties"]["path"]
    assert schema["properties"]["path"]["enum"] == [["right"]]
    ai = service(lambda _: httpx.Response(200, json=response('{"path":["wrong"]}')))
    with pytest.raises(AiExtractionError) as error:
        ai._generate("gemini-3.8-flash", "Read", schema=schema)
    assert error.value.failure_code == "AI_INVALID_CANDIDATES"


@pytest.mark.parametrize("status,reason", [(403, "PERMISSION_DENIED"), (400, "API_KEY_INVALID")])
def test_authentication_failure_is_not_retried_or_exposed(status, reason):
    calls = []
    def handle(request):
        calls.append(request)
        return httpx.Response(status, json={"error": {"message": "secret-key customer-data", "details": [{"reason": reason}]}})
    ai = service(handle)
    with pytest.raises(AiExtractionError) as error:
        ai._generate("gemini-3.8-flash", "Read")
    assert len(calls) == 1
    assert error.value.failure_code == "AI_AUTH_FAILED"
    assert "secret-key" not in str(error.value)


def test_rate_limit_respects_retry_info_and_exhaustion(monkeypatch):
    ai = service(lambda _: httpx.Response(429, headers={"retry-after": "2"},
        json={"error": {"details": [{"retryDelay": "12s"}]}}), ai_max_retries=1)
    waits, cooldowns = [], []
    monkeypatch.setattr(ai._pacer, "wait", waits.append)
    monkeypatch.setattr(ai._pacer, "cooldown", cooldowns.append)
    with pytest.raises(AiExtractionError) as error:
        ai._generate("gemini-3.8-flash", "Read")
    assert len(waits) == 2 and cooldowns == [12, 12]
    assert error.value.failure_code == "AI_RATE_LIMITED"
    assert error.value.retry_after_seconds == 12


@pytest.mark.parametrize("finish,code", [("MAX_TOKENS", "AI_OUTPUT_TRUNCATED"), ("SAFETY", "AI_INVALID_CANDIDATES")])
def test_incomplete_response_never_admits_partial_json(finish, code):
    ai = service(lambda _: httpx.Response(200, json=response('{}', finish)))
    with pytest.raises(AiExtractionError) as error:
        ai._generate("gemini-3.8-flash", "Read", schema={"type": "object"})
    assert error.value.failure_code == code


def test_multiple_job_clients_share_same_pacer():
    a, b = GeminiDocumentService(settings()), GeminiDocumentService(settings())
    assert a._pacer is b._pacer


def test_verifier_uses_configured_verification_model():
    seen = []
    def handle(request):
        seen.append(str(request.url))
        return httpx.Response(200, json=response('{"verdicts":[]}'))
    ai = service(handle, gemini_verification_model="gemini-2.5-pro")
    assert ai.extraction_json('{"questions":[]}') == {"verdicts": []}
    assert seen[0].endswith('/gemini-2.5-pro:generateContent')
