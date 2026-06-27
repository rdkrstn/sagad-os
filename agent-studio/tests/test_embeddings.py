"""EmbeddingService wiring tests.

NOTE: tests/conftest.py permanently patches ``EmbeddingService.embed_text`` to
``deterministic_embedding`` to prevent live OpenAI calls during collection. So these tests
exercise the un-patched ``embedding_model`` property (which routes through
``resolve_embedding_config``) and the dimension resolver, not ``embed_text`` directly. The
embed_text httpx path is verified by the standalone repro in docs/model-providers.md and by
the /model-providers/test endpoint (tests/test_model_providers_api.py).
"""

from __future__ import annotations

from agent_studio.config import Settings
from agent_studio.embeddings import DEV_EMBEDDING_MODEL, EmbeddingService
from agent_studio.model_config import resolve_embedding_dimensions


def test_embedding_model_unconfigured_is_dev_model() -> None:
    svc = EmbeddingService(Settings())  # MODEL_PROVIDER=none
    assert svc.embedding_model == DEV_EMBEDDING_MODEL


def test_embedding_model_fireworks() -> None:
    svc = EmbeddingService(Settings(model_provider="fireworks", fireworks_api_key="fw"))
    assert svc.embedding_model == "nomic-embed-v1"


def test_embedding_model_openai() -> None:
    svc = EmbeddingService(Settings(model_provider="openai", openai_api_key="sk"))
    assert svc.embedding_model == "text-embedding-3-small"


def test_embedding_model_openrouter_falls_back_to_dev() -> None:
    # OpenRouter has no embeddings -> auto resolves to none -> dev model.
    svc = EmbeddingService(Settings(model_provider="openrouter", openrouter_api_key="or"))
    assert svc.embedding_model == DEV_EMBEDDING_MODEL


def test_resolve_embedding_dimensions_known_and_override() -> None:
    assert resolve_embedding_dimensions("nomic-embed-v1") == 768
    assert resolve_embedding_dimensions("text-embedding-3-large") == 3072
    assert resolve_embedding_dimensions("unknown-model") == 1536  # default
    assert resolve_embedding_dimensions("nomic-embed-v1", override=512) == 512
