from __future__ import annotations

import hashlib
import math
import re

import httpx

from agent_studio.config import Settings


TOKEN_PATTERN = re.compile(r"[a-z0-9]+")
EMBEDDING_DIMENSIONS = 1536
DEV_EMBEDDING_MODEL = "sagad-dev-hash-embedding-v1"
OPENAI_EMBEDDINGS_URL = "https://api.openai.com/v1"


def tokenize(value: str) -> set[str]:
    return set(TOKEN_PATTERN.findall(value.lower()))


def content_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def deterministic_embedding(value: str) -> list[float]:
    vector = [0.0] * EMBEDDING_DIMENSIONS
    tokens = TOKEN_PATTERN.findall(value.lower())
    if not tokens:
        return vector

    for token in tokens:
        digest = hashlib.sha256(token.encode("utf-8")).digest()
        index = int.from_bytes(digest[:4], "big") % EMBEDDING_DIMENSIONS
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
        if not content:
            return deterministic_embedding("")
        if not self.settings.openai_api_key:
            return deterministic_embedding(content)

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
        except httpx.HTTPError as exc:
            raise RuntimeError(
                f"OpenAI embedding request failed: {exc.__class__.__name__}",
            ) from exc

        data = payload.get("data")
        if not isinstance(data, list) or not data:
            raise RuntimeError("OpenAI embedding response did not include embedding data.")
        embedding = data[0].get("embedding") if isinstance(data[0], dict) else None
        if not isinstance(embedding, list):
            raise RuntimeError("OpenAI embedding response did not include a vector.")
        values = [float(item) for item in embedding]
        if len(values) != EMBEDDING_DIMENSIONS:
            raise RuntimeError(
                f"Embedding dimension mismatch: expected {EMBEDDING_DIMENSIONS}, got {len(values)}.",
            )
        return values
