"""Single source of truth for model-provider resolution (chat + embeddings).

Both ``graph._build_chat_model`` and ``embeddings.EmbeddingService`` ask this module which
provider/model/credentials to use, so the model layer has one coherent config instead of
scattered ``os.getenv`` precedence. LiteLLM is the chat engine under the hood; this module
maps a chosen provider to the right LiteLLM model prefix + ``api_base`` + ``api_key``.

Provider selection is env-driven (``MODEL_PROVIDER`` / ``EMBEDDING_PROVIDER``). The default
``none`` provider means zero network and zero credentials — the honest open-source default
(chat uses ``DryRunChatModel``; embeddings use the deterministic fallback).

See ``docs/model-providers.md`` for the full provider guide.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from agent_studio.config import Settings

# ---------------------------------------------------------------------------
# Provider vocabulary
# ---------------------------------------------------------------------------

ChatProvider = Literal["none", "openai", "fireworks", "ollama_cloud", "openrouter", "litellm"]
EmbedProvider = Literal["auto", "none", "openai", "fireworks", "ollama_cloud", "litellm"]

CHAT_PROVIDERS: tuple[str, ...] = ("none", "openai", "fireworks", "ollama_cloud", "openrouter", "litellm")
EMBEDDING_PROVIDERS: tuple[str, ...] = ("auto", "none", "openai", "fireworks", "ollama_cloud", "litellm")

DEFAULT_EMBEDDING_DIMENSIONS = 1536
OPENAI_DEFAULT_BASE_URL = "https://api.openai.com/v1"
FIREWORKS_DEFAULT_BASE_URL = "https://api.fireworks.ai/inference/v1"

# Model -> expected embedding dimensions. Unknown models fall back to DEFAULT_EMBEDDING_DIMENSIONS
# (or the explicit EMBEDDING_DIMENSIONS override on Settings).
EMBEDDING_DIMENSIONS_MAP: dict[str, int] = {
    "text-embedding-3-small": 1536,
    "text-embedding-3-large": 3072,
    "text-embedding-ada-002": 1536,
    # Fireworks
    "nomic-embed-v1": 768,
    "nomic-embed-140k": 768,
    "bge-large-en-v1": 1024,
    # Ollama
    "nomic-embed-text": 768,
    "mxbai-embed-large": 1024,
    "bge-m3": 1024,
    "snowflake-arctic-embed": 1024,
}


def resolve_embedding_dimensions(model: str, override: int | None = None) -> int:
    if override is not None and override > 0:
        return override
    return EMBEDDING_DIMENSIONS_MAP.get(model, DEFAULT_EMBEDDING_DIMENSIONS)


# ---------------------------------------------------------------------------
# Resolved config dataclasses
# ---------------------------------------------------------------------------


@dataclass
class ChatModelConfig:
    provider: str
    model: str  # LiteLLM-format, e.g. "fireworks_ai/...", "openrouter/...", "openai/..."
    api_base: str | None
    api_key: str | None
    configured: bool  # False -> caller should use DryRunChatModel (no network)
    detail: str = ""


@dataclass
class EmbeddingConfig:
    provider: str
    base_url: str | None
    api_key: str | None
    model: str
    dimensions: int
    configured: bool  # False -> deterministic fallback, NO network call
    detail: str = ""


@dataclass
class ProviderStatus:
    provider: str
    active: bool  # this is the resolved chat provider
    embedding_active: bool  # this is the resolved embedding provider
    configured: bool  # chat credentials present
    embedding_configured: bool
    base_url: str | None
    model: str | None
    detail: str


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_NODE_MODEL_FIELD = {
    "classifier": "classifier_model",
    "guardrail": "guardrail_model",
    "extractor": "extractor_model",
    "supervisor": "supervisor_model",
}


def _node_model(settings: Settings, node_type: str | None, fallback: str) -> str:
    """Pick the model for a node: per-node override if set, else the provider default."""
    if node_type and node_type in _NODE_MODEL_FIELD:
        override = getattr(settings, _NODE_MODEL_FIELD[node_type], None)
        if override:
            return override
    return fallback


def _prefixed(provider: str, model: str) -> str:
    """Apply the LiteLLM provider prefix to a bare model name (no double-prefixing)."""
    if provider == "litellm":
        return model  # gateway alias, no prefix
    if provider == "openai" or provider == "ollama_cloud":
        return model if model.startswith("openai/") else f"openai/{model}"
    if provider == "fireworks":
        return model if model.startswith("fireworks_ai/") else f"fireworks_ai/{model}"
    if provider == "openrouter":
        return model if model.startswith("openrouter/") else f"openrouter/{model}"
    return model


# ---------------------------------------------------------------------------
# Chat resolution
# ---------------------------------------------------------------------------


def resolve_chat_config(settings: Settings, node_type: str | None = None) -> ChatModelConfig:
    provider = (settings.model_provider or "none").strip().lower()
    if provider not in CHAT_PROVIDERS:
        provider = "none"

    if provider == "none":
        return ChatModelConfig(
            provider="none",
            model="",
            api_base=None,
            api_key=None,
            configured=False,
            detail="MODEL_PROVIDER=none — zero network, zero credentials (DryRun).",
        )
    if provider == "openai":
        model = _node_model(settings, node_type, settings.openai_model or "gpt-4o-mini")
        api_key = settings.openai_api_key
        api_base = (settings.openai_base_url or None)
        configured = bool(api_key) and bool(model)
        return ChatModelConfig(
            provider="openai",
            model=_prefixed("openai", model),
            api_base=api_base,
            api_key=api_key,
            configured=configured,
            detail=("OpenAI direct." if configured else "OPENAI_API_KEY not set — chat degrades to DryRun."),
        )
    if provider == "fireworks":
        model = _node_model(settings, node_type, settings.fireworks_model)
        api_key = settings.fireworks_api_key
        api_base = settings.fireworks_base_url or FIREWORKS_DEFAULT_BASE_URL
        configured = bool(api_key) and bool(model)
        return ChatModelConfig(
            provider="fireworks",
            model=_prefixed("fireworks", model),
            api_base=api_base,
            api_key=api_key,
            configured=configured,
            detail=("Fireworks AI." if configured else "FIREWORKS_API_KEY not set — chat degrades to DryRun."),
        )
    if provider == "ollama_cloud":
        model = _node_model(settings, node_type, settings.ollama_cloud_model)
        api_key = settings.ollama_cloud_api_key
        api_base = settings.ollama_cloud_base_url
        configured = bool(api_base) and bool(model)  # api_key optional (local Ollama has none)
        return ChatModelConfig(
            provider="ollama_cloud",
            model=_prefixed("ollama_cloud", model),
            api_base=api_base,
            api_key=api_key,
            configured=configured,
            detail=("Ollama Cloud / local Ollama." if configured else "OLLAMA_CLOUD_BASE_URL not set — chat degrades to DryRun."),
        )
    if provider == "openrouter":
        model = _node_model(settings, node_type, settings.openrouter_model)
        api_key = settings.openrouter_api_key
        configured = bool(api_key) and bool(model)
        return ChatModelConfig(
            provider="openrouter",
            model=_prefixed("openrouter", model),
            api_base=None,  # LiteLLM knows the OpenRouter endpoint
            api_key=api_key,
            configured=configured,
            detail=("OpenRouter." if configured else "OPENROUTER_API_KEY not set — chat degrades to DryRun."),
        )
    # litellm gateway
    model = _node_model(settings, node_type, settings.litellm_model or "")
    api_base = settings.litellm_base_url
    api_key = settings.litellm_master_key
    configured = bool(api_base) and bool(model)
    return ChatModelConfig(
        provider="litellm",
        model=model,
        api_base=api_base,
        api_key=api_key,
        configured=configured,
        detail=("LiteLLM gateway." if configured else "LITELLM_BASE_URL + LITELLM_MODEL not set — chat degrades to DryRun."),
    )


# ---------------------------------------------------------------------------
# Embedding resolution
# ---------------------------------------------------------------------------


def _resolve_embedding_provider(settings: Settings) -> str:
    requested = (settings.embedding_provider or "auto").strip().lower()
    if requested not in EMBEDDING_PROVIDERS:
        requested = "auto"
    if requested != "auto":
        return requested
    # auto: follow the chat provider; openrouter + none have no embeddings endpoint.
    chat = (settings.model_provider or "none").strip().lower()
    if chat in {"openai", "fireworks", "ollama_cloud", "litellm"}:
        return chat
    return "none"


def resolve_embedding_config(settings: Settings) -> EmbeddingConfig:
    provider = _resolve_embedding_provider(settings)
    dims_override = settings.embedding_dimensions

    if provider == "none":
        return EmbeddingConfig(
            provider="none",
            base_url=None,
            api_key=None,
            model="",
            dimensions=resolve_embedding_dimensions("", dims_override),
            configured=False,
            detail="No embedding provider — deterministic fallback, no network.",
        )
    if provider == "openai":
        model = settings.openai_embedding_model or "text-embedding-3-small"
        api_key = settings.openai_api_key
        base_url = (settings.openai_base_url or OPENAI_DEFAULT_BASE_URL).rstrip("/")
        configured = bool(api_key) and bool(model)
        return EmbeddingConfig(
            provider="openai",
            base_url=base_url,
            api_key=api_key,
            model=model,
            dimensions=resolve_embedding_dimensions(model, dims_override),
            configured=configured,
            detail=("OpenAI embeddings." if configured else "OPENAI_API_KEY not set — deterministic fallback."),
        )
    if provider == "fireworks":
        model = settings.fireworks_embedding_model or "nomic-embed-v1"
        api_key = settings.fireworks_api_key
        base_url = (settings.fireworks_base_url or FIREWORKS_DEFAULT_BASE_URL).rstrip("/")
        configured = bool(api_key) and bool(model)
        return EmbeddingConfig(
            provider="fireworks",
            base_url=base_url,
            api_key=api_key,
            model=model,
            dimensions=resolve_embedding_dimensions(model, dims_override),
            configured=configured,
            detail=("Fireworks embeddings." if configured else "FIREWORKS_API_KEY not set — deterministic fallback."),
        )
    if provider == "ollama_cloud":
        model = settings.ollama_cloud_embedding_model or "nomic-embed-text"
        api_key = settings.ollama_cloud_api_key
        base_url = (settings.ollama_cloud_base_url or "").rstrip("/") or None
        configured = bool(base_url) and bool(model)
        return EmbeddingConfig(
            provider="ollama_cloud",
            base_url=base_url,
            api_key=api_key,
            model=model,
            dimensions=resolve_embedding_dimensions(model, dims_override),
            configured=configured,
            detail=("Ollama embeddings." if configured else "OLLAMA_CLOUD_BASE_URL not set — deterministic fallback."),
        )
    # litellm
    model = settings.litellm_embedding_model or ""
    api_key = settings.litellm_master_key
    base_url = (settings.litellm_base_url or "").rstrip("/") or None
    configured = bool(base_url) and bool(model)
    return EmbeddingConfig(
        provider="litellm",
        base_url=base_url,
        api_key=api_key,
        model=model,
        dimensions=resolve_embedding_dimensions(model, dims_override),
        configured=configured,
        detail=("LiteLLM embeddings." if configured else "LITELLM_BASE_URL + LITELLM_EMBEDDING_MODEL not set — deterministic fallback."),
    )


# ---------------------------------------------------------------------------
# Console status
# ---------------------------------------------------------------------------


def _chat_configured(settings: Settings, provider: str) -> tuple[bool, str | None, str | None]:
    """Return (configured, base_url, model) for a provider's chat creds."""
    if provider == "openai":
        return bool(settings.openai_api_key) and bool(settings.openai_model), settings.openai_base_url, settings.openai_model
    if provider == "fireworks":
        return bool(settings.fireworks_api_key), settings.fireworks_base_url, settings.fireworks_model
    if provider == "ollama_cloud":
        return bool(settings.ollama_cloud_base_url), settings.ollama_cloud_base_url, settings.ollama_cloud_model
    if provider == "openrouter":
        return bool(settings.openrouter_api_key), None, settings.openrouter_model
    if provider == "litellm":
        return bool(settings.litellm_base_url) and bool(settings.litellm_model), settings.litellm_base_url, settings.litellm_model
    return False, None, None


def _embedding_configured(settings: Settings, provider: str) -> bool:
    if provider == "none":
        return False
    cfg = resolve_embedding_config(settings.model_copy(update={"embedding_provider": provider}))
    return cfg.configured


def provider_status(settings: Settings) -> list[ProviderStatus]:
    active_chat = (settings.model_provider or "none").strip().lower()
    active_embed = _resolve_embedding_provider(settings)
    statuses: list[ProviderStatus] = []
    for provider in CHAT_PROVIDERS:
        if provider == "none":
            statuses.append(
                ProviderStatus(
                    provider="none",
                    active=active_chat == "none",
                    embedding_active=active_embed == "none",
                    configured=True,
                    embedding_configured=False,
                    base_url=None,
                    model=None,
                    detail="Zero-credential default (DryRun chat + deterministic embeddings).",
                )
            )
            continue
        chat_ok, base_url, model = _chat_configured(settings, provider)
        embed_ok = _embedding_configured(settings, provider)
        kind_note = "chat + embeddings" if embed_ok else ("chat only" if chat_ok else "not configured")
        statuses.append(
            ProviderStatus(
                provider=provider,
                active=active_chat == provider,
                embedding_active=active_embed == provider,
                configured=chat_ok,
                embedding_configured=embed_ok,
                base_url=base_url,
                model=model,
                detail=kind_note,
            )
        )
    return statuses
