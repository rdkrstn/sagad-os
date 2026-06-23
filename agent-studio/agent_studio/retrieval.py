from typing import Protocol

from langchain_core.documents import Document
from psycopg.types.json import Jsonb

from agent_studio.config import Settings, get_settings
from agent_studio.db import (
    TrustedContext,
    connect,
    database_configured,
    initialize_database,
    initialize_database_safe,
    resolve_trusted_context,
    set_app_context,
)
from agent_studio.embeddings import (
    EmbeddingService,
    TOKEN_PATTERN,
    content_hash,
    tokenize,
    vector_literal,
)
from agent_studio.knowledge import KnowledgeRecord, load_knowledge_records, to_documents
from agent_studio.schemas import KnowledgeHit


class KnowledgeRetrieverProtocol(Protocol):
    records: list[KnowledgeRecord]

    def add_record(self, record: KnowledgeRecord) -> None:
        ...

    def remove_record(self, record_id: str) -> None:
        ...

    def search(
        self,
        query: str,
        *,
        intent: str,
        risk_level: str,
        limit: int = 4,
        context: TrustedContext | None = None,
    ) -> list[KnowledgeHit]:
        ...


def _rerank_hits(
    query: str,
    hits: list[KnowledgeHit],
    limit: int,
    settings: Settings,
) -> list[KnowledgeHit]:
    if not hits or not settings.rerank_enabled:
        return hits[:limit]

    import os
    documents = [hit.excerpt for hit in hits]
    results = None

    # Check if we should use direct OpenRouter call
    is_openrouter = (
        "openrouter" in settings.rerank_model
        or (settings.rerank_api_key and settings.rerank_api_key.startswith("sk-or-"))
        or (os.getenv("OPENROUTER_API_KEY") and not settings.rerank_api_key)
    )

    if is_openrouter:
        try:
            import httpx

            model_name = settings.rerank_model.removeprefix("openrouter/")
            api_key = settings.rerank_api_key or os.getenv("OPENROUTER_API_KEY")

            if api_key:
                headers = {
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json"
                }
                payload = {
                    "model": model_name,
                    "query": query,
                    "documents": documents,
                    "top_n": limit
                }
                with httpx.Client(timeout=10.0) as client:
                    res = client.post("https://openrouter.ai/api/v1/rerank", headers=headers, json=payload)
                    res.raise_for_status()
                    data = res.json()
                    results = data.get("results", [])
        except Exception as e:
            print(f"Direct OpenRouter rerank failed: {e}. Trying LiteLLM fallback...")

    # Fallback to LiteLLM rerank if direct call was not made or failed
    if results is None:
        try:
            import litellm
            kwargs = {
                "model": settings.rerank_model,
                "query": query,
                "documents": documents,
                "top_n": limit,
            }
            if settings.rerank_api_key:
                kwargs["api_key"] = settings.rerank_api_key

            if settings.litellm_enabled and settings.litellm_base_url:
                kwargs["api_base"] = settings.litellm_base_url
                if settings.litellm_master_key:
                    kwargs["api_key"] = settings.litellm_master_key

            response = litellm.rerank(**kwargs)
            results = getattr(response, "results", None) or response.get("results", [])
        except Exception as e:
            print(f"LiteLLM reranking failed: {e}")
            return hits[:limit]

    # Re-order hits based on results — copy before mutating to avoid side-effects
    try:
        reranked = []
        for item in results:
            idx = getattr(item, "index", None)
            if idx is None and isinstance(item, dict):
                idx = item.get("index")
            score = getattr(item, "relevance_score", None)
            if score is None and isinstance(item, dict):
                score = item.get("relevance_score")

            if idx is not None and idx < len(hits):
                # Copy the hit to avoid mutating the original score
                hit = hits[idx].model_copy(update={"score": float(score)})
                reranked.append(hit)

        if not reranked:
            return hits[:limit]

        return reranked
    except Exception as e:
        print(f"Failed to process reranker results: {e}")
        return hits[:limit]


class InMemoryKnowledgeRetriever:
    def __init__(self, records: list[KnowledgeRecord] | None = None, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.records = records if records is not None else load_knowledge_records()
        self.documents: list[Document] = to_documents(self.records)

    def add_record(self, record: KnowledgeRecord) -> None:
        self.records = [existing for existing in self.records if existing.id != record.id]
        self.records.append(record)
        self.documents = to_documents(self.records)

    def remove_record(self, record_id: str) -> None:
        self.records = [existing for existing in self.records if existing.id != record_id]
        self.documents = to_documents(self.records)

    def search(
        self,
        query: str,
        *,
        intent: str,
        risk_level: str,
        limit: int = 4,
        context: TrustedContext | None = None,
    ) -> list[KnowledgeHit]:
        query_tokens = tokenize(f"{query} {intent} {risk_level}")
        scored: list[tuple[float, Document]] = []

        for document in self.documents:
            if str(document.metadata.get("approval_status", "approved")) != "approved":
                continue
            doc_tokens = tokenize(document.page_content)
            overlap = len(query_tokens.intersection(doc_tokens))
            category = str(document.metadata.get("category", "general"))
            category_boost = 1.0 if category in {"compliance", "sops", "qa"} else 0.0
            if intent in document.page_content.lower():
                category_boost += 2.0
            score = float(overlap) + category_boost
            if score > 0:
                scored.append((score, document))

        scored.sort(key=lambda item: item[0], reverse=True)
        candidate_limit = max(limit, 15) if self.settings.rerank_enabled else limit
        hits = [self._to_hit(document, score) for score, document in scored[:candidate_limit]]
        if self.settings.rerank_enabled:
            return _rerank_hits(query, hits, limit, self.settings)
        return hits[:limit]

    def _to_hit(self, document: Document, score: float) -> KnowledgeHit:
        content = document.page_content.strip().replace("\n", " ")
        excerpt = content[:280] + ("..." if len(content) > 280 else "")
        return KnowledgeHit(
            id=str(document.metadata["id"]),
            title=str(document.metadata["title"]),
            category=str(document.metadata["category"]),
            source_path=str(document.metadata["source_path"]),
            score=score,
            excerpt=excerpt,
        )


class PostgresKnowledgeRetriever:
    def __init__(self, settings: Settings, records: list[KnowledgeRecord] | None = None) -> None:
        self.settings = settings
        self.embedding_service = EmbeddingService(settings)
        self.records = records if records is not None else load_knowledge_records()
        self.fallback = InMemoryKnowledgeRetriever(self.records, settings=settings)
        # Non-fatal init; only sync seed records if migrations succeeded (otherwise the
        # fallback in-memory retriever stays usable and readiness reports not-ready).
        if initialize_database_safe(settings):
            self._sync_records()

    def add_record(self, record: KnowledgeRecord) -> None:
        self.fallback.add_record(record)

    def remove_record(self, record_id: str) -> None:
        self.fallback.remove_record(record_id)

    def search(
        self,
        query: str,
        *,
        intent: str,
        risk_level: str,
        limit: int = 4,
        context: TrustedContext | None = None,
    ) -> list[KnowledgeHit]:
        embedding = vector_literal(
            self.embedding_service.embed_text(f"{query} {intent} {risk_level}"),
        )
        embedding_model = self.embedding_service.embedding_model
        with connect(self.settings) as connection:
            resolved_context = resolve_trusted_context(connection, context)
            set_app_context(connection, resolved_context)
            retrieval_run_id = connection.execute(
                """
                INSERT INTO retrieval_runs (
                  organization_id,
                  query,
                  intent,
                  risk_level,
                  filters,
                  embedding_model
                )
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                (
                    resolved_context.organization_id,
                    query,
                    intent,
                    risk_level,
                    Jsonb({"category": "approved_governed_knowledge"}),
                    embedding_model,
                ),
            ).fetchone()["id"]
            rows = connection.execute(
                """
                SELECT
                  knowledge_chunks.id,
                  knowledge_documents.title,
                  knowledge_documents.category,
                  knowledge_documents.source_path,
                  knowledge_chunks.content,
                  1 - (knowledge_chunk_embeddings.embedding <=> %s::vector) AS score
                FROM knowledge_chunk_embeddings
                JOIN knowledge_chunks
                  ON knowledge_chunks.id = knowledge_chunk_embeddings.chunk_id
                JOIN knowledge_documents
                  ON knowledge_documents.id = knowledge_chunks.document_id
                WHERE knowledge_documents.organization_id = %s
                  AND knowledge_documents.approval_status = 'approved'
                  AND knowledge_chunk_embeddings.embedding_model = %s
                  AND knowledge_chunk_embeddings.embedding IS NOT NULL
                  AND (
                    knowledge_documents.metadata->'intents' IS NULL
                    OR knowledge_documents.metadata->'intents' ? %s
                    OR knowledge_documents.metadata->>'intent' = %s
                  )
                  AND (
                    knowledge_documents.metadata->'risk_levels' IS NULL
                    OR knowledge_documents.metadata->'risk_levels' ? %s
                    OR knowledge_documents.metadata->>'risk_level' = %s
                  )
                ORDER BY knowledge_chunk_embeddings.embedding <=> %s::vector
                LIMIT %s
                """,
                (
                    embedding,
                    resolved_context.organization_id,
                    embedding_model,
                    intent,
                    intent,
                    risk_level,
                    risk_level,
                    embedding,
                    max(limit, 15) if self.settings.rerank_enabled else limit,
                ),
            ).fetchall()
            hits = [self._hit_from_row(row) for row in rows]
            if self.settings.rerank_enabled:
                hits = _rerank_hits(query, hits, limit, self.settings)
            else:
                hits = hits[:limit]
            for rank, hit in enumerate(hits, start=1):
                connection.execute(
                    """
                    INSERT INTO retrieval_hits (
                      organization_id,
                      retrieval_run_id,
                      chunk_id,
                      rank,
                      score,
                      excerpt,
                      metadata
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        resolved_context.organization_id,
                        retrieval_run_id,
                        hit.id,
                        rank,
                        hit.score,
                        hit.excerpt,
                        Jsonb(
                            {
                                "title": hit.title,
                                "category": hit.category,
                                "source_path": hit.source_path,
                            },
                        ),
                    ),
                )
            connection.commit()

        return hits if hits else self.fallback.search(
            query,
            intent=intent,
            risk_level=risk_level,
            limit=limit,
            context=context,
        )

    def _sync_records(self) -> None:
        with connect(self.settings) as connection:
            context = resolve_trusted_context(connection, None)
            set_app_context(connection, context)
            for record in self.records:
                document_hash = content_hash(record.content)
                chunk_id = f"{record.id}:chunk:0"
                connection.execute(
                    """
                    INSERT INTO knowledge_documents (
                      id,
                      organization_id,
                      pack_slug,
                      category,
                      source_path,
                      title,
                      content,
                      content_hash,
                      approval_status,
                      metadata
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'approved', %s)
                    ON CONFLICT (id) DO UPDATE SET
                      category = EXCLUDED.category,
                      source_path = EXCLUDED.source_path,
                      title = EXCLUDED.title,
                      content = EXCLUDED.content,
                      content_hash = EXCLUDED.content_hash,
                      approval_status = EXCLUDED.approval_status,
                      metadata = EXCLUDED.metadata,
                      updated_at = now()
                    """,
                    (
                        record.id,
                        context.organization_id,
                        "seed-knowledge",
                        record.category,
                        record.source_path,
                        record.title,
                        record.content,
                        document_hash,
                        Jsonb({}),
                    ),
                )
                connection.execute(
                    """
                    INSERT INTO knowledge_chunks (
                      id,
                      organization_id,
                      document_id,
                      chunk_index,
                      heading,
                      content,
                      content_hash,
                      token_count,
                      metadata
                    )
                    VALUES (%s, %s, %s, 0, %s, %s, %s, %s, %s)
                    ON CONFLICT (document_id, chunk_index) DO UPDATE SET
                      heading = EXCLUDED.heading,
                      content = EXCLUDED.content,
                      content_hash = EXCLUDED.content_hash,
                      token_count = EXCLUDED.token_count,
                      metadata = EXCLUDED.metadata,
                      updated_at = now()
                    """,
                    (
                        chunk_id,
                        context.organization_id,
                        record.id,
                        record.title,
                        record.content,
                        document_hash,
                        len(TOKEN_PATTERN.findall(record.content.lower())),
                        Jsonb({}),
                    ),
                )
                connection.execute(
                    """
                    INSERT INTO knowledge_chunk_embeddings (
                      chunk_id,
                      organization_id,
                      embedding_model,
                      embedding,
                      content_hash
                    )
                    VALUES (%s, %s, %s, %s::vector, %s)
                    ON CONFLICT (chunk_id, embedding_model) DO UPDATE SET
                      embedding = EXCLUDED.embedding,
                      content_hash = EXCLUDED.content_hash,
                      updated_at = now()
                    """,
                    (
                        chunk_id,
                        context.organization_id,
                        self.embedding_service.embedding_model,
                        vector_literal(self.embedding_service.embed_text(record.content)),
                        document_hash,
                    ),
                )
            connection.commit()

    def _hit_from_row(self, row: dict[str, object]) -> KnowledgeHit:
        content = str(row["content"]).strip().replace("\n", " ")
        excerpt = content[:280] + ("..." if len(content) > 280 else "")
        score = row["score"]
        return KnowledgeHit(
            id=str(row["id"]),
            title=str(row["title"]),
            category=str(row["category"]),
            source_path=str(row["source_path"]),
            score=float(score) if isinstance(score, (int, float)) else 0.0,
            excerpt=excerpt,
        )


from functools import lru_cache


def build_retriever(settings: Settings | None = None) -> KnowledgeRetrieverProtocol:
    scoped_settings = settings or get_settings()
    if database_configured(scoped_settings):
        return PostgresKnowledgeRetriever(scoped_settings)
    return InMemoryKnowledgeRetriever()


@lru_cache
def get_retriever(settings: Settings | None = None) -> KnowledgeRetrieverProtocol:
    """Lazily initialise and cache the retriever.

    Unlike the module-level ``retriever`` pattern this avoids DB-connection
    attempts at import time so FastAPI health checks and test runners can
    boot without a database.
    """
    return build_retriever(settings)


# Legacy module-level retriever — defaults to in-memory to avoid DB-connection
# hangs at import time (psycopg2 blocks 30s on unreachable hosts).
#
# Graph code should call ``get_retriever()`` for the real (potentially
# Postgres-backed) retriever.  Module-level importers get an in-memory
# retriever as a safe fallback.
retriever: KnowledgeRetrieverProtocol = InMemoryKnowledgeRetriever()
