from agent_studio.memory_workflow import build_memory_pack, memory_items_from_record
from agent_studio.schemas import ConversationMessageRecord, ConversationRecord, MemoryHit


def test_build_memory_pack_prioritizes_relevant_thread_context() -> None:
    pack = build_memory_pack(
        current_message="I already said pricing.",
        recent_messages=[
            ConversationMessageRecord(
                sender_type="customer",
                body="hmmm pricing",
                external_message_id="msg-1",
            ),
            ConversationMessageRecord(
                sender_type="ai_agent",
                body="Which service should I price for you?",
            ),
        ],
        durable_memory=[
            MemoryHit(
                memory_type="prior_intent",
                content="Customer was asking about pricing.",
                source="memory",
                score=0.72,
            ),
        ],
        limit=3,
    )

    assert pack.memory_context
    assert pack.memory_context[0].memory_type in {"recent_customer_message", "prior_intent"}
    assert any("pricing" in hit.content.lower() for hit in pack.memory_context)
    assert pack.memory_diagnostic["memory_available"] is True
    assert pack.memory_diagnostic["selected_count"] >= 1


def test_memory_items_from_record_keeps_operational_context_not_policy() -> None:
    record = ConversationRecord(
        incoming_message="I need pricing for an AC tune-up.",
        normalized_message="I need pricing for an AC tune-up.",
        intent="pricing_lead",
        risk_level="low",
        selected_agent="sales_agent",
        customer_driver="pricing or quote",
        draft_reply="What service are you pricing?",
    )

    items = memory_items_from_record(record, lifecycle_event="draft_created")

    assert {item.memory_type for item in items} >= {
        "prior_intent",
        "unresolved_ask",
        "resolution_state",
    }
    assert all("policy" not in item.memory_type for item in items)
    assert any("pricing or quote" in item.content.lower() for item in items)
