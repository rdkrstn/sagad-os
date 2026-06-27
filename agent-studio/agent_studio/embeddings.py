from __future__ import annotations

import hashlib
import logging
import math
import re

import httpx

from agent_studio.config import Settings
# The dimension map + resolver live in model_config (single source of truth for chat +
# embeddings). Re-exported here so existing imports keep working.
from agent_studio.model_config import (
    DEFAULT_EMBEDDING_DIMENSIONS,
    EMBEDDING_DIMENSIONS_MAP,
    resolve_embedding_config,
    resolve_embedding_dimensions,
)

_log = logging.getLogger(__name__)


TOKEN_PATTERN = re.compile(r"[a-z0-9]+")
DEV_EMBEDDING_DIMENSIONS = 1536
DEV_EMBEDDING_MODEL = "sagad-dev-hash-embedding-v1"


def tokenize(value: str) -> set[str]:
    return set(TOKEN_PATTERN.findall(value.lower()))


def content_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def deterministic_embedding(value: str, dimensions: int = DEFAULT_EMBEDDING_DIMENSIONS) -> list[float]:
    vector = [0.0] * dimensions
    tokens = TOKEN_PATTERN.findall(value.lower())
    if not tokens:
        return vector

    for token in tokens:
        digest = hashlib.sha256(token.encode("utf-8")).digest()
        index = int.from_bytes(digest[:4], "big") % dimensions
        sign = 1.0 if digest[4] % 2 == 0 else -1.0
        vector[index] += sign

    magnitude = math.sqrt(sum(item * item for item in vector))
    if magnitude == 0:
        return vector
    return [item / magnitude for item in vector]


def vector_literal(values: list[float]) -> str:
    return "[" + ",".join(f"{value:.8f}" for value in values) + "]"


class EmbeddingService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    @property
    def embedding_model(self) -> str:
        cfg = resolve_embedding_config(self.settings)
        return cfg.model if (cfg.configured and cfg.model) else DEV_EMBEDDING_MODEL

    def embed_text(self, value: str) -> list[float]:
        """Embed text via the resolved provider, or the deterministic fallback.

        When no embedding provider is configured (``EMBEDDING_PROVIDER=none`` or the active
        provider has no creds), this makes **no network call** — it returns the deterministic
        hash embedding so the pipeline never 500s and never silently hangs on a dead endpoint.
        """
        content = value.strip()
        cfg = resolve_embedding_config(self.settings)
        if not content:
            return deterministic_embedding("", dimensions=cfg.dimensions)
        if not cfg.configured:
            return deterministic_embedding(content, dimensions=cfg.dimensions)

        headers = {"Content-Type": "application/json"}
        if cfg.api_key:
            headers["Authorization"] = f"Bearer {cfg.api_key}"
        try:
            with httpx.Client(timeout=30) as client:
                response = client.post(
                    f"{cfg.base_url}/embeddings",
                    headers=headers,
                    json={
                        "model": cfg.model,
                        "input": content,
                        "encoding_format": "float",
                    },
                )
                response.raise_for_status()
                payload = response.json()
            data = payload.get("data")
            if not isinstance(data, list) or not data:
                raise RuntimeError("Embedding response did not include embedding data.")
            embedding = data[0].get("embedding") if isinstance(data[0], dict) else None
            if not isinstance(embedding, list):
                raise RuntimeError("Embedding response did not include a vector.")
            values = [float(item) for item in embedding]
            if len(values) != cfg.dimensions:
                raise RuntimeError(
                    f"Embedding dimension mismatch for model '{cfg.model}': "
                    f"expected {cfg.dimensions}, got {len(values)}.",
                )
            return values
        except Exception as exc:
            # A dead/unreachable endpoint must never break the pipeline (webhook, retrieval,
            # memory). Fall back to the dimension-aligned deterministic embedding; semantic
            # recall is degraded but nothing 500s. The warning names provider + base_url so the
            # failure is diagnosable. Configure a reachable EMBEDDING_PROVIDER to restore real
            # embeddings.
            _log.warning(
                "embed_text_failed provider=%s base_url=%s model=%s error=%s -> falling back to deterministic embedding",
                cfg.provider,
                cfg.base_url,
                cfg.model,
                exc.__class__.__name__,
            )
            return deterministic_embedding(content, dimensions=cfg.dimensions)


__all__ = [
    "DEFAULT_EMBEDDING_DIMENSIONS",
    "DEV_EMBEDDING_DIMENSIONS",
    "DEV_EMBEDDING_MODEL",
    "EMBEDDING_DIMENSIONS_MAP",
    "EmbeddingService",
    "content_hash",
    "deterministic_embedding",
    "resolve_embedding_dimensions",
    "tokenize",
    "vector_literal",
]
