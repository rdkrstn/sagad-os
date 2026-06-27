"""API tests for /model-providers (status), /model-providers/test, and PUT (writable config).

Uses InMemory stores (DATABASE_URL is loaded via dotenv in this env; without a live Postgres
the Postgres stores would time out). Model-provider config is DB-backed via the InMemory store.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from agent_studio.config import get_settings
from agent_studio.integration_config import InMemoryIntegrationConfigStore
from agent_studio.main import app
from agent_studio.model_provider_config import InMemoryModelProviderConfigStore

client = TestClient(app)


@pytest.fixture(autouse=True)
def _in_memory_store(monkeypatch: pytest.MonkeyPatch):
    store = InMemoryIntegrationConfigStore()
    mp_store = InMemoryModelProviderConfigStore()
    monkeypatch.setattr("agent_studio.integration_config.integration_config_store", store)
    monkeypatch.setattr("agent_studio.main.integration_config_store", store)
    monkeypatch.setattr("agent_studio.integration_config.model_provider_config_store", mp_store)
    monkeypatch.setattr("agent_studio.main.model_provider_config_store", mp_store)
    get_settings.cache_clear()
    yield mp_store


def _setenv(monkeypatch: pytest.MonkeyPatch, **env: str) -> None:
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    get_settings.cache_clear()


def test_model_providers_list_default_none() -> None:
    response = client.get("/model-providers", headers={"X-Sagad-Role": "owner"})
    assert response.status_code == 200
    body = response.json()
    assert body["active"] == "none"
    assert len(body["providers"]) == 6


def test_model_providers_requires_admin() -> None:
    response = client.get("/model-providers", headers={"X-Sagad-Role": "viewer"})
    assert response.status_code == 403


def test_model_providers_test_none_is_honest() -> None:
    response = client.post("/model-providers/test", headers={"X-Sagad-Role": "owner"})
    assert response.status_code == 200
    body = response.json()
    assert body["chat"]["ok"] is False
    assert body["embedding"]["ok"] is False


def test_model_providers_test_openai_chat_ok(monkeypatch: pytest.MonkeyPatch) -> None:
    _setenv(monkeypatch, MODEL_PROVIDER="openai", OPENAI_API_KEY="sk", EMBEDDING_PROVIDER="none")
    with patch("litellm.completion") as mock_completion:
        mock_completion.return_value = MagicMock()
        response = client.post("/model-providers/test", headers={"X-Sagad-Role": "owner"})
    assert response.status_code == 200
    body = response.json()
    assert body["chat"]["ok"] is True
    assert body["embedding"]["ok"] is False  # EMBEDDING_PROVIDER=none -> not configured


def test_model_providers_list_marks_active_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    _setenv(monkeypatch, MODEL_PROVIDER="fireworks", FIREWORKS_API_KEY="fw")
    response = client.get("/model-providers", headers={"X-Sagad-Role": "owner"})
    body = response.json()
    assert body["active"] == "fireworks"
    active = [row for row in body["providers"] if row["active"]]
    assert len(active) == 1 and active[0]["provider"] == "fireworks"
    assert active[0]["configured"] is True


def test_put_model_providers_then_get_reflects() -> None:
    response = client.put(
        "/model-providers",
        headers={"X-Sagad-Role": "owner"},
        json={
            "chat_provider": "fireworks",
            "embedding_provider": "none",
            "fireworks_api_key": "fw-secret",
            "fireworks_model": "accounts/fireworks/models/deepseek-v4",
        },
    )
    assert response.status_code == 200
    assert response.json()["active"] == "fireworks"

    got = client.get("/model-providers", headers={"X-Sagad-Role": "owner"})
    body = got.json()
    assert body["active"] == "fireworks"
    assert body["config"]["fireworks"]["has_api_key"] is True
    assert body["config"]["fireworks"]["model"] == "accounts/fireworks/models/deepseek-v4"
    # Raw secret must never reach the browser.
    assert "fw-secret" not in got.text


def test_put_model_providers_requires_admin() -> None:
    response = client.put(
        "/model-providers",
        headers={"X-Sagad-Role": "viewer"},
        json={"chat_provider": "fireworks"},
    )
    assert response.status_code == 403


def test_test_endpoint_uses_db_config_after_put() -> None:
    client.put(
        "/model-providers",
        headers={"X-Sagad-Role": "owner"},
        json={"chat_provider": "openai", "embedding_provider": "none", "openai_api_key": "sk"},
    )
    with patch("litellm.completion") as mock_completion:
        mock_completion.return_value = MagicMock()
        response = client.post("/model-providers/test", headers={"X-Sagad-Role": "owner"})
    body = response.json()
    assert body["chat"]["ok"] is True  # DB-configured openai + mocked litellm
    assert body["embedding"]["ok"] is False  # embedding_provider=none
