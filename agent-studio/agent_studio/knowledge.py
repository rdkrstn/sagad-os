from dataclasses import dataclass
from pathlib import Path
import re

from langchain_core.documents import Document


@dataclass(frozen=True)
class KnowledgeRecord:
    id: str
    title: str
    category: str
    source_path: str
    content: str
    approval_status: str = "approved"


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def default_knowledge_root() -> Path:
    return _repo_root() / "knowledge" / "packs" / "home-services"


def _title_from_markdown(content: str, fallback: str) -> str:
    for line in content.splitlines():
        if line.startswith("# "):
            return line.removeprefix("# ").strip()
    return fallback


def _clean_content(content: str) -> str:
    return re.sub(r"\n{3,}", "\n\n", content).strip()


def load_knowledge_records(root: Path | None = None) -> list[KnowledgeRecord]:
    knowledge_root = root or default_knowledge_root()
    records: list[KnowledgeRecord] = []

    for path in sorted(knowledge_root.rglob("*.md")):
        relative_path = path.relative_to(knowledge_root)
        category = relative_path.parts[0] if len(relative_path.parts) > 1 else "general"
        content = _clean_content(path.read_text(encoding="utf-8"))
        title = _title_from_markdown(content, path.stem.replace("-", " ").title())
        record_id = f"{category}:{path.stem}"
        records.append(
            KnowledgeRecord(
                id=record_id,
                title=title,
                category=category,
                source_path=str(relative_path).replace("\\", "/"),
                content=content,
                approval_status="approved",
            ),
        )

    return records


def to_documents(records: list[KnowledgeRecord]) -> list[Document]:
    return [
        Document(
            page_content=record.content,
            metadata={
                "id": record.id,
                "title": record.title,
                "category": record.category,
                "source_path": record.source_path,
                "approval_status": record.approval_status,
            },
        )
        for record in records
    ]
