from types import SimpleNamespace

import pytest
from pydantic import SecretStr

from app.config import Settings
from app.mistral_service import (
    AiExtractionError,
    MistralDocumentService,
    is_transient_error,
)
from app.schema_service import parse_output_contract


def test_settings_preserve_unique_key_order():
    settings = Settings(
        mistral_api_keys=SecretStr("primary, secondary, primary"),
        mistral_api_key=SecretStr("legacy"),
        _env_file=None,
    )

    assert settings.mistral_key_values == ["primary", "secondary", "legacy"]
    assert settings.ai_configured is True


def test_structured_extraction_falls_back_to_second_key(monkeypatch):
    attempts: list[str] = []

    class FakeChat:
        def __init__(self, key: str):
            self.key = key

        def complete(self, **_kwargs):
            attempts.append(self.key)
            if self.key == "primary":
                raise RuntimeError("primary unavailable")
            message = SimpleNamespace(
                content='{"data":{"status":"ok"},"evidence":[],"warnings":[]}'
            )
            return SimpleNamespace(choices=[SimpleNamespace(message=message)])

    class FakeMistral:
        def __init__(self, api_key: str):
            self.chat = FakeChat(api_key)

    monkeypatch.setattr("app.mistral_service.Mistral", FakeMistral)
    settings = Settings(
        mistral_api_keys=SecretStr("primary,secondary"),
        mistral_api_key=None,
        _env_file=None,
    )
    service = MistralDocumentService(settings)

    result = service._chat_json("extract")

    assert result.data == {"status": "ok"}
    assert attempts == ["primary", "secondary"]


def test_user_schema_is_sent_as_strict_response_contract(monkeypatch):
    captured: dict = {}

    class FakeChat:
        def complete(self, **kwargs):
            captured.update(kwargs)
            message = SimpleNamespace(
                content='{"data":{"name":null},"evidence":[],"warnings":[]}'
            )
            return SimpleNamespace(choices=[SimpleNamespace(message=message)])

    class FakeMistral:
        def __init__(self, api_key: str):
            self.chat = FakeChat()

    monkeypatch.setattr("app.mistral_service.Mistral", FakeMistral)
    settings = Settings(mistral_api_key=SecretStr("test"), _env_file=None)
    service = MistralDocumentService(settings)
    contract = parse_output_contract(
        '{"type":"object","properties":{"name":{"type":"string"}}}'
    )

    result = service._chat_json("extract", contract)

    assert result.data == {"name": None}
    assert captured["response_format"]["type"] == "json_schema"
    assert captured["response_format"]["json_schema"]["strict"] is True


def test_structured_extraction_normalizes_empty_ai_values(monkeypatch):
    class FakeChat:
        def complete(self, **_kwargs):
            message = SimpleNamespace(
                content=(
                    '{"data":null,"evidence":['
                    '{"label":"Missing quote","page":2,"evidence":null},'
                    '{"label":null,"page":3,"evidence":"Total: 42"}'
                    '],"warnings":[null,"Amount is ambiguous"]}'
                )
            )
            return SimpleNamespace(choices=[SimpleNamespace(message=message)])

    class FakeMistral:
        def __init__(self, api_key: str):
            self.chat = FakeChat()

    monkeypatch.setattr("app.mistral_service.Mistral", FakeMistral)
    settings = Settings(mistral_api_key=SecretStr("test"), _env_file=None)
    service = MistralDocumentService(settings)

    result = service._chat_json("extract")

    assert result.data == {}
    assert [item.model_dump() for item in result.evidence] == [
        {"label": "Finding", "page": 3, "evidence": "Total: 42"}
    ]
    assert result.warnings == ["Amount is ambiguous"]


def test_vision_page_uses_multimodal_text_model(monkeypatch):
    captured: dict = {}

    class FakeChat:
        def complete(self, **kwargs):
            captured.update(kwargs)
            message = SimpleNamespace(content="Transcribed page text")
            return SimpleNamespace(choices=[SimpleNamespace(message=message)])

    class FakeMistral:
        def __init__(self, api_key: str):
            self.chat = FakeChat()

    monkeypatch.setattr("app.mistral_service.Mistral", FakeMistral)
    settings = Settings(mistral_api_key=SecretStr("test"), _env_file=None)
    service = MistralDocumentService(settings)

    text = service.vision_page_text("data:image/jpeg;base64,abc", 3)

    assert text == "Transcribed page text"
    assert captured["model"] == settings.mistral_text_model
    content = captured["messages"][0]["content"]
    assert content[1] == {
        "type": "image_url",
        "image_url": "data:image/jpeg;base64,abc",
    }


class RateLimited(RuntimeError):
    status_code = 429


class BadRequest(RuntimeError):
    status_code = 400


def test_rate_limited_call_is_retried_with_backoff(monkeypatch):
    attempts: list[str] = []
    delays: list[float] = []
    monkeypatch.setattr("app.mistral_service.time.sleep", delays.append)

    class FakeChat:
        def __init__(self, key: str):
            self.key = key

        def complete(self, **_kwargs):
            attempts.append(self.key)
            if len(attempts) < 3:
                raise RateLimited("Requests rate limit exceeded")
            message = SimpleNamespace(
                content='{"data":{"status":"ok"},"evidence":[],"warnings":[]}'
            )
            return SimpleNamespace(choices=[SimpleNamespace(message=message)])

    class FakeMistral:
        def __init__(self, api_key: str):
            self.chat = FakeChat(api_key)

    monkeypatch.setattr("app.mistral_service.Mistral", FakeMistral)
    settings = Settings(
        mistral_api_keys=SecretStr("primary,secondary"),
        mistral_api_key=None,
        _env_file=None,
    )
    service = MistralDocumentService(settings)

    result = service._chat_json("extract")

    assert result.data == {"status": "ok"}
    assert attempts == ["primary", "secondary", "primary"]
    assert len(delays) == 1


def test_client_errors_are_not_retried(monkeypatch):
    attempts: list[str] = []
    monkeypatch.setattr("app.mistral_service.time.sleep", lambda _seconds: None)

    class FakeChat:
        def __init__(self, key: str):
            self.key = key

        def complete(self, **_kwargs):
            attempts.append(self.key)
            raise BadRequest("Invalid request payload")

    class FakeMistral:
        def __init__(self, api_key: str):
            self.chat = FakeChat(api_key)

    monkeypatch.setattr("app.mistral_service.Mistral", FakeMistral)
    settings = Settings(mistral_api_key=SecretStr("only"), _env_file=None)
    service = MistralDocumentService(settings)

    with pytest.raises(AiExtractionError):
        service._chat_json("extract")

    assert attempts == ["only"]


def test_transient_classification():
    assert is_transient_error(RateLimited("slow down")) is True
    assert is_transient_error(BadRequest("bad")) is False
    assert is_transient_error(RuntimeError("Connection reset by peer")) is True
    assert is_transient_error(RuntimeError("Unauthorized")) is False
