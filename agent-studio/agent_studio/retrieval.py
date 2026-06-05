from typing import Protocol

from langchain_core.documents import Document
from psycopg.types.json import Jsonb

from agent_studio.config import Settings, get_settings
from agent_studio.db import (
    connect,
    database_configured,
    initialize_database,
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

    def search(
        self,
        query: str,
        *,
        intent: str,
        risk_level: str,
        limit: int = 4,
    ) -> list[KnowledgeHit]:
        ...


class InMemoryKnowledgeRetriever:
    def __init__(self, records: list[KnowledgeRecord] | None = None) -> None:
        self.records = records if records is not None else load_knowledge_records()
        self.documents: list[Document] = to_documents(self.records)

    def add_record(self, record: KnowledgeRecord) -> None:
        self.records = [existing for existing in self.records if existing.id != record.id]
        self.records.append(record)
        self.documents = to_documents(self.records)

    def search(
        self,
        query: str,
        *,
        intent: str,
        risk_level: str,
        limit: int = 4,
    ) -> list[KnowledgeHit]:
        query_tokens = tokenize(f"{query} {intent} {risk_level}")
        scored: list[tuple[float, Document]] = []

        for document in self.documents:
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
        return [self._to_hit(document, score) for score, document in scored[:limit]]

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
        self.fallback = InMemoryKnowledgeRetriever(self.records)
        initialize_database(settings)
        self._sync_records()

    def search(
        self,
        query: str,
        *,
        intent: str,
        risk_level: str,
        limit: int = 4,
    ) -> list[KnowledgeHit]:
        embedding = vector_literal(
            self.embedding_service.embed_text(f"{query} {intent} {risk_level}"),
        )
        embedding_model = self.embedding_service.embedding_model
        with connect(self.settings) as connection:
            context = resolve_trusted_context(connection, None)
            set_app_context(connection, context)
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
                    context.organization_id,
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
                    context.organization_id,
                    embedding_model,
                    intent,
                    intent,
                    risk_level,
                    risk_level,
                    embedding,
                    limit,
                ),
            ).fetchall()
            hits = [self._hit_from_row(row) for row in rows]
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
                        context.organization_id,
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
                        "home-services",
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


def build_retriever(settings: Settings | None = None) -> KnowledgeRetrieverProtocol:
    scoped_settings = settings or get_settings()
    if database_configured(scoped_settings):
        return PostgresKnowledgeRetriever(scoped_settings)
    return InMemoryKnowledgeRetriever()


retriever = build_retriever()
