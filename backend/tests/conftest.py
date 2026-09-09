import pytest

from app import main


@pytest.fixture(autouse=True)
def isolate_service_settings(monkeypatch):
    """Keep tests independent of whatever sits in the developer's backend/.env.

    Auth-related tests opt in by overriding these themselves; everything else
    should behave the same whether or not the local .env turns the service mode on.
    """
    monkeypatch.setattr(main.settings, "require_api_key", False, raising=False)
    monkeypatch.setattr(main.settings, "admin_token", None, raising=False)
    # Legacy fixtures mock Mistral; Gemini tests select their provider explicitly.
    # A developer switching providers must never make offline tests call a live API.
    monkeypatch.setenv("AI_PROVIDER", "mistral")
    monkeypatch.setattr(main.settings, "ai_provider", "mistral")
