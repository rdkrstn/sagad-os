"""Conversation memory workflow helpers.

Memory is operational customer/thread context. It is intentionally separate
from the approved KB/SOP retrieval path in ``retrieval_workflow``.
"""

from __future__ import annotations

from dataclasses import dataclass

from agent_studio.embeddings import tokenize
from agent_studio.schemas import ConversationMessageRecord, ConversationRecord, MemoryHit


MEMORY_TYPE_WEIGHT = {
    "recent_customer_message": 0.45,
    "unresolved_ask": 0.40,
    "prior_intent": 0.35,
    "approved_reply": 0.30,
    "resolution_state": 0.25,
}


@dataclass(frozen=True)
class MemoryPack:
    memory_context: list[MemoryHit]
    memory_diagnostic: dict[str, object]


def _bounded_score(value: float) -> float:
    return round(max(0.0, min(1.0, value)), 4)


def _overlap_score(query: str, content: str) -> float:
    query_tokens = tokenize(query)
    content_tokens = tokenize(content)
    if not query_tokens or not content_tokens:
        return 0.0
    overlap = len(query_tokens.intersection(content_tokens))
    return min(0.45, overlap / max(len(query_tokens), 1))


def _message_to_memory_hit(
    message: ConversationMessageRecord,
    *,
    conversation_id: str | None,
    chatwoot_conversation_id: str | None,
    reverse_index: int,
) -> MemoryHit:
    if message.sender_type == "customer":
        memory_type = "recent_customer_message"
    elif message.sender_type == "ai_agent":
        memory_type = "approved_reply"
    else:
        memory_type = "resolution_state"
    recency_score = max(0.0, 0.20 - (reverse_index * 0.03))
    return MemoryHit(
        memory_type=memory_type,
        content=message.body,
        source="thread",
        score=_bounded_score(MEMORY_TYPE_WEIGHT.get(memory_type, 0.2) + recency_score),
        conversation_id=conversation_id,
        chatwoot_conversation_id=chatwoot_conversation_id,
        source_message_id=message.external_message_id or message.id,
        metadata={"sender_type": message.sender_type},
        created_at=message.created_at,
    )


def build_memory_pack(
    *,
    current_message: str,
    recent_messages: list[ConversationMessageRecord] | None = None,
    durable_memory: list[MemoryHit] | None = None,
    conversation_id: str | None = None,
    chatwoot_conversation_id: str | None = None,
    limit: int = 5,
) -> MemoryPack:
    candidates: list[MemoryHit] = []
    recent = recent_messages or []
    for reverse_index, message in enumerate(reversed(recent[-8:])):
        if not message.body.strip():
            continue
        candidates.append(
            _message_to_memory_hit(
                message,
                conversation_id=conversation_id,
                chatwoot_conversation_id=chatwoot_conversation_id,
                reverse_index=reverse_index,
            ),
        )
    candidates.extend(durable_memory or [])

    scored: list[MemoryHit] = []
    for hit in candidates:
        score = max(
            hit.score,
            _bounded_score(
                MEMORY_TYPE_WEIGHT.get(hit.memory_type, 0.2)
                + _overlap_score(current_message, hit.content),
            ),
        )
        scored.append(hit.model_copy(update={"score": score}))

    scored.sort(key=lambda item: (item.score, item.created_at), reverse=True)
    selected = scored[: max(limit, 0)]
    return MemoryPack(
        memory_context=selected,
        memory_diagnostic={
            "workflow": "memory_workflow",
            "memory_available": bool(selected),
            "candidate_count": len(candidates),
            "selected_count": len(selected),
            "reasons": [
                "ranked recent thread messages and durable conversation memory",
            ]
            if selected
            else ["no prior thread or durable memory available"],
        },
    )


def memory_items_from_record(
    record: ConversationRecord,
    *,
    lifecycle_event: str,
) -> list[MemoryHit]:
    items: list[MemoryHit] = []
    if record.customer_driver or record.intent:
        driver = record.customer_driver or record.intent.replace("_", " ")
        items.append(
            MemoryHit(
                memory_type="prior_intent",
                content=f"Customer driver: {driver}.",
                source="agent_studio",
                score=0.78,
                conversation_id=record.id,
                chatwoot_conversation_id=record.chatwoot_conversation_id,
                metadata={
                    "intent": record.intent,
                    "selected_agent": record.selected_agent,
                    "lifecycle_event": lifecycle_event,
                },
            ),
        )
    if record.incoming_message.strip():
        items.append(
            MemoryHit(
                memory_type="unresolved_ask",
                content=record.incoming_message.strip(),
                source="customer",
                score=0.82,
                conversation_id=record.id,
                chatwoot_conversation_id=record.chatwoot_conversation_id,
                source_message_id=record.chatwoot_message_id,
                metadata={"lifecycle_event": lifecycle_event},
            ),
        )
    if lifecycle_event == "approved_send" and record.draft_reply.strip():
        items.append(
            MemoryHit(
                memory_type="approved_reply",
                content=record.draft_reply.strip(),
                source="supervisor_approved_reply",
                score=0.74,
                conversation_id=record.id,
                chatwoot_conversation_id=record.chatwoot_conversation_id,
                metadata={
                    "send_status": record.send_status,
                    "approval_status": record.approval_status,
                    "lifecycle_event": lifecycle_event,
                },
            ),
        )
    state_content = {
        "draft_created": f"Draft pending supervisor approval for {record.customer_driver or record.intent}.",
        "approved_send": f"Supervisor approved reply; send status is {record.send_status}.",
        "resolved": "Conversation was manually resolved by a supervisor.",
    }.get(lifecycle_event)
    if state_content:
        items.append(
            MemoryHit(
                memory_type="resolution_state",
                content=state_content,
                source="agent_studio",
                score=0.64,
                conversation_id=record.id,
                chatwoot_conversation_id=record.chatwoot_conversation_id,
                metadata={
                    "lifecycle_event": lifecycle_event,
                    "approval_status": record.approval_status,
                    "send_status": record.send_status,
                },
            ),
        )
    return items


__all__ = ["MemoryPack", "build_memory_pack", "memory_items_from_record"]
