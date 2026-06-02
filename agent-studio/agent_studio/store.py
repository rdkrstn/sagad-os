from datetime import datetime, timezone

from agent_studio.schemas import ConversationRecord


class ConversationStore:
    def __init__(self) -> None:
        self._records: dict[str, ConversationRecord] = {}

    def list(self) -> list[ConversationRecord]:
        return sorted(
            self._records.values(),
            key=lambda record: record.updated_at,
            reverse=True,
        )

    def get(self, conversation_id: str) -> ConversationRecord | None:
        return self._records.get(conversation_id)

    def save(self, record: ConversationRecord) -> ConversationRecord:
        record.updated_at = datetime.now(timezone.utc)
        self._records[record.id] = record
        return record

    def clear(self) -> None:
        self._records.clear()


store = ConversationStore()
