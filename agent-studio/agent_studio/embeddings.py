from __future__ import annotations

import hashlib
import logging
import math
import re

import httpx

from agent_studio.config import Settings

_log = logging.getLogger(__name__)


TOKEN_PATTERN = re.compile(r"[a-z0-9]+")
DEV_EMBEDDING_DIMENSIONS = 1536
DEFAULT_EMBEDDING_DIMENSIONS = 1536
DEV_EMBEDDING_MODEL = "sagad-dev-hash-embedding-v1"
OPENAI_EMBEDDINGS_URL = "https://api.openai.com/v1"

# Model-to-dimension map for known embedding models
EMBEDDING_DIMENSIONS_MAP: dict[str, int] = {
    "text-embedding-3-small": 1536,
    "text-embedding-3-large": 3072,
    "text-embedding-ada-002": 1536,
    DEV_EMBEDDING_MODEL: DEV_EMBEDDING_DIMENSIONS,
}


def resolve_embedding_dimensions(embedding_model: str) -> int:
    """Return the expected dimension for a known embedding model, or fall back to default."""
    return EMBEDDING_DIMENSIONS_MAP.get(embedding_model, DEFAULT_EMBEDDING_DIMENSIONS)


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
        if not self.settings.openai_api_key:
            return DEV_EMBEDDING_MODEL
        return self.settings.openai_embedding_model

    def embed_text(self, value: str) -> list[float]:
        content = value.strip()
        model_name = self.embedding_model
        expected_dims = resolve_embedding_dimensions(model_name)
        if not content:
            return deterministic_embedding("", dimensions=expected_dims)
        if not self.settings.openai_api_key:
            return deterministic_embedding(content, dimensions=expected_dims)

        base_url = (self.settings.openai_base_url or OPENAI_EMBEDDINGS_URL).rstrip("/")
        try:
            with httpx.Client(timeout=30) as client:
                response = client.post(
                    f"{base_url}/embeddings",
                    headers={
                        "Authorization": f"Bearer {self.settings.openai_api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": self.settings.openai_embedding_model,
                        "input": content,
                        "encoding_format": "float",
                    },
                )
                response.raise_for_status()
                payload = response.json()
            data = payload.get("data")
            if not isinstance(data, list) or not data:
                raise RuntimeError("OpenAI embedding response did not include embedding data.")
            embedding = data[0].get("embedding") if isinstance(data[0], dict) else None
            if not isinstance(embedding, list):
                raise RuntimeError("OpenAI embedding response did not include a vector.")
            values = [float(item) for item in embedding]
            if len(values) != expected_dims:
                raise RuntimeError(
                    f"Embedding dimension mismatch for model '{model_name}': "
                    f"expected {expected_dims}, got {len(values)}.",
                )
            return values
        except Exception as exc:
            # An invalid/unreachable OpenAI key must not break the pipeline (webhook,
            # retrieval, memory). Fall back to the dimension-aligned deterministic
            # embedding so the request still succeeds; semantic recall is degraded
            # but nothing 500s. Set a valid OPENAI_API_KEY to restore real embeddings.
            _log.warning(
                "embed_text_openai_failed model=%s error=%s -> falling back to deterministic embedding",
                model_name,
                exc.__class__.__name__,
            )
            return deterministic_embedding(content, dimensions=expected_dims)
