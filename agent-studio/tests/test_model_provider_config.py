"""DB-backed model-provider config tests (InMemory stores, no Postgres required)."""

from __future__ import annotations

import json

import pytest

from agent_studio.config import get_settings
from agent_studio.integration_config import (
    InMemoryIntegrationConfigStore,
    configured_settings,
)
from agent_studio.model_config import resolve_chat_config
from agent_studio.model_provider_config import (
    InMemoryModelProviderConfigStore,
    model_provider_config_view,
)
from agent_studio.schemas import ModelProviderConfigUpsertRequest


@pytest.fixture(autouse=True)
def _in_memory_stores(monkeypatch: pytest.MonkeyPatch):
    ic_store = InMemoryIntegrationConfigStore()
    mp_store = InMemoryModelProviderConfigStore()
    monkeypatch.setattr("agent_studio.integration_config.integration_config_store", ic_store)
    monkeypatch.setattr("agent_studio.main.integration_config_store", ic_store)
    monkeypatch.setattr("agent_studio.integration_config.model_provider_config_store", mp_store)
    monkeypatch.setattr("agent_studio.main.model_provider_config_store", mp_store)
    get_settings.cache_clear()
    yield mp_store


def test_upsert_then_get_roundtrip() -> None:
    mp = InMemoryModelProviderConfigStore()
    record = mp.upsert(
        ModelProviderConfigUpsertRequest(
            chat_provider="fireworks",
            fireworks_api_key="fw-secret",
            fireworks_model="accounts/fireworks/models/deepseek-v4",
        )
    )
    assert record.chat_provider == "fireworks"
    assert record.config["fireworks_model"] == "accounts/fireworks/models/deepseek-v4"
    assert record.secrets["fireworks_api_key"] == "fw-secret"

    fetched = mp.get()
    assert fetched is not None
    assert fetched.chat_provider == "fireworks"
    assert fetched.secrets["fireworks_api_key"] == "fw-secret"


def test_view_does_not_leak_secrets() -> None:
    mp = InMemoryModelProviderConfigStore()
    record = mp.upsert(
        ModelProviderConfigUpsertRequest(chat_provider="fireworks", fireworks_api_key="fw-secret")
    )
    view = model_provider_config_view(record, get_settings())
    assert view["fireworks"]["has_api_key"] is True
    # No raw secret anywhere in the console-safe view.
    assert "fw-secret" not in json.dumps(view, default=str)


def test_configured_settings_overrides_env(_in_memory_stores) -> None:
    _in_memory_stores.upsert(
        ModelProviderConfigUpsertRequest(
            chat_provider="fireworks",
            fireworks_api_key="fw-db",
            fireworks_model="accounts/fireworks/models/deepseek-v4",
        )
    )
    get_settings.cache_clear()
    # env default is MODEL_PROVIDER=none; DB must win.
    settings = configured_settings(get_settings(), context=None)
    assert settings.model_provider == "fireworks"
    assert settings.fireworks_api_key == "fw-db"
    chat = resolve_chat_config(settings)
    assert chat.provider == "fireworks"
    assert chat.configured is True
    assert chat.model == "fireworks_ai/accounts/fireworks/models/deepseek-v4"


def test_env_fallback_when_no_row(_in_memory_stores, monkeypatch: pytest.MonkeyPatch) -> None:
    _in_memory_stores.clear()
    monkeypatch.setenv("MODEL_PROVIDER", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-env")
    get_settings.cache_clear()
    settings = configured_settings(get_settings(), context=None)
    assert settings.model_provider == "openai"
    assert settings.openai_api_key == "sk-env"


def test_secret_blank_keeps_stored_value(_in_memory_stores) -> None:
    _in_memory_stores.upsert(
        ModelProviderConfigUpsertRequest(chat_provider="fireworks", fireworks_api_key="fw-secret")
    )
    # Second save with an empty secret value must not wipe the stored key.
    _in_memory_stores.upsert(
        ModelProviderConfigUpsertRequest(chat_provider="fireworks", fireworks_api_key="")
    )
    record = _in_memory_stores.get()
    assert record is not None
    assert record.secrets["fireworks_api_key"] == "fw-secret"


def test_partial_update_preserves_existing_config(_in_memory_stores) -> None:
    _in_memory_stores.upsert(
        ModelProviderConfigUpsertRequest(
            chat_provider="fireworks",
            fireworks_model="accounts/fireworks/models/deepseek-v4",
            fireworks_api_key="fw",
        )
    )
    # A later save that only changes the active provider keeps the stored model.
    _in_memory_stores.upsert(ModelProviderConfigUpsertRequest(chat_provider="openai"))
    record = _in_memory_stores.get()
    assert record is not None
    assert record.chat_provider == "openai"
    assert record.config["fireworks_model"] == "accounts/fireworks/models/deepseek-v4"
    assert record.secrets["fireworks_api_key"] == "fw"
