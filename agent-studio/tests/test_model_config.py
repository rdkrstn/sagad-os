"""Unit tests for agent_studio.model_config — the chat + embedding provider resolver."""

from __future__ import annotations

from agent_studio.config import Settings
from agent_studio.model_config import (
    provider_status,
    resolve_chat_config,
    resolve_embedding_config,
)


def s(**kwargs) -> Settings:
    return Settings(**kwargs)


# --- chat ---


def test_chat_none_is_unconfigured() -> None:
    cfg = resolve_chat_config(s(model_provider="none"))
    assert cfg.provider == "none"
    assert cfg.configured is False


def test_chat_unknown_provider_degrades_to_none() -> None:
    cfg = resolve_chat_config(s(model_provider="garbage"))
    assert cfg.provider == "none"
    assert cfg.configured is False


def test_chat_openai() -> None:
    cfg = resolve_chat_config(s(model_provider="openai", openai_api_key="sk"))
    assert cfg.configured is True
    assert cfg.provider == "openai"
    assert cfg.model == "openai/gpt-4o-mini"
    assert cfg.api_key == "sk"


def test_chat_openai_missing_key_is_unconfigured() -> None:
    cfg = resolve_chat_config(s(model_provider="openai"))
    assert cfg.configured is False


def test_chat_fireworks() -> None:
    cfg = resolve_chat_config(s(model_provider="fireworks", fireworks_api_key="fw"))
    assert cfg.configured is True
    assert cfg.model.startswith("fireworks_ai/")
    assert cfg.api_base == "https://api.fireworks.ai/inference/v1"
    assert cfg.api_key == "fw"


def test_chat_ollama_cloud_local_no_key() -> None:
    cfg = resolve_chat_config(
        s(model_provider="ollama_cloud", ollama_cloud_base_url="http://localhost:11434/v1")
    )
    assert cfg.configured is True
    assert cfg.model.startswith("openai/")
    assert cfg.api_base == "http://localhost:11434/v1"
    assert cfg.api_key is None  # local Ollama has no key


def test_chat_openrouter() -> None:
    cfg = resolve_chat_config(s(model_provider="openrouter", openrouter_api_key="or"))
    assert cfg.configured is True
    assert cfg.model == "openrouter/openai/gpt-4o-mini"
    assert cfg.api_base is None  # litellm knows the endpoint


def test_chat_litellm_alias_no_prefix() -> None:
    cfg = resolve_chat_config(
        s(
            model_provider="litellm",
            litellm_base_url="http://litellm:4000/v1",
            litellm_model="sagad-openai-fast",
        )
    )
    assert cfg.configured is True
    assert cfg.model == "sagad-openai-fast"  # no provider prefix for gateway aliases
    assert cfg.api_base == "http://litellm:4000/v1"


def test_chat_litellm_missing_model_unconfigured() -> None:
    cfg = resolve_chat_config(s(model_provider="litellm", litellm_base_url="http://litellm:4000/v1"))
    assert cfg.configured is False


def test_chat_per_node_override_applies_provider_prefix() -> None:
    cfg = resolve_chat_config(
        s(
            model_provider="fireworks",
            fireworks_api_key="fw",
            classifier_model="accounts/fireworks/models/qwen2.5-72b",
        ),
        node_type="classifier",
    )
    assert cfg.model == "fireworks_ai/accounts/fireworks/models/qwen2.5-72b"


# --- embeddings ---


def test_embedding_auto_follows_chat_fireworks() -> None:
    cfg = resolve_embedding_config(s(model_provider="fireworks", fireworks_api_key="fw"))
    assert cfg.provider == "fireworks"
    assert cfg.configured is True
    assert cfg.base_url == "https://api.fireworks.ai/inference/v1"
    assert cfg.model == "nomic-embed-v1"
    assert cfg.dimensions == 768


def test_embedding_auto_openrouter_falls_to_none() -> None:
    cfg = resolve_embedding_config(s(model_provider="openrouter", openrouter_api_key="or"))
    assert cfg.provider == "none"
    assert cfg.configured is False


def test_embedding_none_is_unconfigured() -> None:
    cfg = resolve_embedding_config(s(embedding_provider="none"))
    assert cfg.configured is False


def test_embedding_explicit_override_when_chat_is_openrouter() -> None:
    cfg = resolve_embedding_config(
        s(
            model_provider="openrouter",
            openrouter_api_key="or",
            embedding_provider="fireworks",
            fireworks_api_key="fw",
        )
    )
    assert cfg.provider == "fireworks"
    assert cfg.configured is True


def test_embedding_dimensions_override() -> None:
    cfg = resolve_embedding_config(
        s(model_provider="fireworks", fireworks_api_key="fw", embedding_dimensions=512)
    )
    assert cfg.dimensions == 512


def test_embedding_ollama_local() -> None:
    cfg = resolve_embedding_config(
        s(
            model_provider="ollama_cloud",
            ollama_cloud_base_url="http://localhost:11434/v1",
        )
    )
    assert cfg.provider == "ollama_cloud"
    assert cfg.configured is True
    assert cfg.model == "nomic-embed-text"
    assert cfg.api_key is None


# --- provider_status ---


def test_provider_status_six_rows_one_active() -> None:
    statuses = provider_status(s(model_provider="fireworks", fireworks_api_key="fw"))
    assert len(statuses) == 6
    active = [row for row in statuses if row.active]
    assert len(active) == 1
    assert active[0].provider == "fireworks"
    assert active[0].configured is True


def test_provider_status_none_active_by_default() -> None:
    statuses = provider_status(s())
    active = [row for row in statuses if row.active]
    assert len(active) == 1
    assert active[0].provider == "none"
