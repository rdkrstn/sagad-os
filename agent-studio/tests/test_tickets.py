"""RevOps ticket queue + PATCH endpoint tests (POST /webhooks/ghl -> PATCH .../ticket).

Follows the test_universal_webhook.py harness: `graph.ainvoke` is mocked so the suite runs
fast with no credentials and no GPU. The in-memory store is used (DATABASE_URL unset), which
also exercises the ticket-field preservation logic in InMemoryConversationStore.save.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from agent_studio.config import get_settings
from agent_studio.integration_config import integration_config_store
from agent_studio.main import app
from agent_studio.store import store

client = TestClient(app)


def setup_function() -> None:
    store.clear()
    integration_config_store.clear()
    get_settings.cache_clear()


def _ghl_payload(*, message_id: str = "msg-1", conv_id: str = "conv-ticket") -> dict[str, object]:
    return {
        "type": "InboundMessage",
        "conversationId": conv_id,
        "locationId": "loc-1",
        "message": {"id": message_id, "body": "Do you do oil changes?", "direction": "inbound", "type": "SMS"},
        "contact": {"id": "cont-1", "name": "Jane Doe"},
    }


def _final_state(*, intent: str = "support_general", risk: str = "low") -> dict[str, object]:
    return {
        "customer_name": "Jane Doe",
        "channel": "sms",
        "incoming_message": "Do you do oil changes?",
        "normalized_message": "oil change question",
        "intent": intent,
        "risk_level": risk,
        "retrieved_knowledge": [],
        "draft_reply": "Yes, oil changes start at $39.",
        "qa_findings": [],
        "compliance_status": "needs_review",
        "retrieval_confidence": 0.70,
        "final_confidence_score": 0.70,
        "trace_url": None,
    }


def _create_conversation() -> str:
    with patch("agent_studio.main.graph.ainvoke", new=AsyncMock(return_value=_final_state())):
        response = client.post("/webhooks/ghl", json=_ghl_payload())
    assert response.status_code == 200, response.text
    return response.json()["id"]


def test_new_conversation_is_an_open_ticket_by_default() -> None:
    conv_id = _create_conversation()
    record = client.get(f"/conversations/{conv_id}").json()
    assert record["ticket_status"] == "open"
    assert record["assignee"] is None
    assert record["priority"] is None
    assert record["pipeline_stage"] is None
    assert record["sla_due_at"] is None


def test_patch_updates_ticket_fields() -> None:
    conv_id = _create_conversation()
    response = client.patch(
        f"/conversations/{conv_id}/ticket",
        json={
            "assignee": "alice",
            "priority": "high",
            "ticket_status": "in_progress",
            "pipeline_stage": "triage",
        },
    )
    assert response.status_code == 200, response.text
    updated = response.json()
    assert updated["assignee"] == "alice"
    assert updated["priority"] == "high"
    assert updated["ticket_status"] == "in_progress"
    assert updated["pipeline_stage"] == "triage"


def test_patch_persists_and_is_visible_on_get() -> None:
    conv_id = _create_conversation()
    client.patch(
        f"/conversations/{conv_id}/ticket",
        json={"assignee": "alice", "ticket_status": "waiting"},
    )
    record = client.get(f"/conversations/{conv_id}").json()
    assert record["assignee"] == "alice"
    assert record["ticket_status"] == "waiting"


def test_patch_records_diagnostic_event() -> None:
    conv_id = _create_conversation()
    client.patch(
        f"/conversations/{conv_id}/ticket",
        json={"assignee": "alice", "supervisor_id": "sup-1"},
    )
    events = store.list_events(conversation_id=conv_id)
    assert any(event.event_type == "ticket.updated" for event in events)


def test_queue_filters_by_ticket_status() -> None:
    conv_id = _create_conversation()
    client.patch(f"/conversations/{conv_id}/ticket", json={"ticket_status": "in_progress"})

    open_tickets = client.get("/conversations?ticket_status=open").json()["conversations"]
    in_progress = client.get("/conversations?ticket_status=in_progress").json()["conversations"]
    assert all(c["id"] != conv_id for c in open_tickets)
    assert any(c["id"] == conv_id for c in in_progress)


def test_queue_filters_by_assignee_and_priority() -> None:
    conv_id = _create_conversation()
    client.patch(
        f"/conversations/{conv_id}/ticket",
        json={"assignee": "alice", "priority": "urgent"},
    )
    by_assignee = client.get("/conversations?assignee=alice").json()["conversations"]
    by_other = client.get("/conversations?assignee=bob").json()["conversations"]
    by_priority = client.get("/conversations?priority=urgent").json()["conversations"]
    assert any(c["id"] == conv_id for c in by_assignee)
    assert all(c["id"] != conv_id for c in by_other)
    assert any(c["id"] == conv_id for c in by_priority)


def test_patch_missing_conversation_returns_404() -> None:
    response = client.patch("/conversations/conv_does_not_exist/ticket", json={"assignee": "x"})
    assert response.status_code == 404


def test_inbound_resave_does_not_clobber_ticket_fields() -> None:
    # Regression guard: a second inbound message on the same conversation must not reset a
    # supervisor's ticket assignment back to defaults (the inbound pipeline never manages tickets).
    conv_id = _create_conversation()
    client.patch(
        f"/conversations/{conv_id}/ticket",
        json={"assignee": "alice", "priority": "high", "ticket_status": "in_progress"},
    )
    # Second inbound message in the same GHL conversation.
    with patch("agent_studio.main.graph.ainvoke", new=AsyncMock(return_value=_final_state())):
        response = client.post("/webhooks/ghl", json=_ghl_payload(message_id="msg-2", conv_id="conv-ticket"))
    assert response.status_code == 200
    record = client.get(f"/conversations/{conv_id}").json()
    assert record["assignee"] == "alice"
    assert record["priority"] == "high"
    assert record["ticket_status"] == "in_progress"


def test_patch_invalid_priority_rejected_by_schema() -> None:
    conv_id = _create_conversation()
    response = client.patch(
        f"/conversations/{conv_id}/ticket",
        json={"priority": "sky-high"},  # not a valid TicketPriority
    )
    assert response.status_code == 422