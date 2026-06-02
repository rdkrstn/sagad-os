import re

from langchain_core.documents import Document

from agent_studio.knowledge import KnowledgeRecord, load_knowledge_records, to_documents
from agent_studio.schemas import KnowledgeHit


TOKEN_PATTERN = re.compile(r"[a-z0-9]+")


def tokenize(value: str) -> set[str]:
    return set(TOKEN_PATTERN.findall(value.lower()))


class InMemoryKnowledgeRetriever:
    def __init__(self, records: list[KnowledgeRecord] | None = None) -> None:
        self.records = records if records is not None else load_knowledge_records()
        self.documents: list[Document] = to_documents(self.records)

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


retriever = InMemoryKnowledgeRetriever()
