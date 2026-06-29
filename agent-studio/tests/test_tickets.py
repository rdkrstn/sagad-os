"""RevOps ticket queue + PATCH endpoint tests (POST /webhooks/ghl -> PATCH .../ticket).

Follows the test_universal_webhook.py harness: `graph.ainvoke` is mocked so the suite runs
fast with no credentials and no GPU. The in-memory store is used (DATABASE_URL unset), which
also exercises the ticket-field preservation logic in InMemoryConversationStore.save.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from agent_studio.config import get_settings
from agent_studio.integration_config import integration_config_store
from agent_studio.main import app
from agent_studio.schemas import ConversationRecord
from agent_studio import store as store_module
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


# --- Phase 2: SLA computation, auto-assignment, transition validation -----------------


def _save_record(record: ConversationRecord) -> ConversationRecord:
    return store.save(record)


def test_sla_due_set_from_priority_on_creation() -> None:
    # A brand-new ticket with a priority but no explicit deadline derives sla_due_at from the
    # priority's SLA window (urgent = 2h) and surfaces a runtime sla_status on read.
    saved = _save_record(
        ConversationRecord(id="conv-sla", incoming_message="hi", priority="urgent")
    )
    assert saved.sla_due_at is not None
    delta = saved.sla_due_at - datetime.now(timezone.utc)
    assert timedelta(hours=1, minutes=55) < delta < timedelta(hours=2, minutes=5)

    fetched = client.get("/conversations/conv-sla").json()
    assert fetched["sla_due_at"] is not None
    assert fetched["sla_status"] == "on_track"


def test_priority_change_recomputes_sla_unless_override() -> None:
    conv_id = _create_conversation()
    # No priority at creation -> no SLA deadline.
    assert client.get(f"/conversations/{conv_id}").json()["sla_due_at"] is None

    # PATCH priority with no explicit deadline -> SLA recomputed from the new priority (high=8h).
    updated = client.patch(
        f"/conversations/{conv_id}/ticket", json={"priority": "high"}
    ).json()
    assert updated["sla_due_at"] is not None
    delta = datetime.fromisoformat(updated["sla_due_at"]) - datetime.now(timezone.utc)
    assert timedelta(hours=7, minutes=55) < delta < timedelta(hours=8, minutes=5)

    # An explicit sla_due_at is honored even when priority is also supplied (no recompute).
    explicit = datetime.now(timezone.utc) + timedelta(hours=48)
    overridden = client.patch(
        f"/conversations/{conv_id}/ticket",
        json={"priority": "urgent", "sla_due_at": explicit.isoformat()},
    ).json()
    returned = datetime.fromisoformat(overridden["sla_due_at"].replace("Z", "+00:00"))
    assert abs((returned - explicit).total_seconds()) < 5  # explicit value, not now+2h


def test_queue_filters_overdue() -> None:
    # One ticket already past its deadline, one healthy on-track ticket.
    past = datetime.now(timezone.utc) - timedelta(hours=1)
    _save_record(
        ConversationRecord(
            id="conv-overdue", incoming_message="hi", priority="high", sla_due_at=past
        )
    )
    _save_record(ConversationRecord(id="conv-ok", incoming_message="hi", priority="low"))

    overdue = client.get("/conversations?overdue=true").json()["conversations"]
    overdue_ids = [c["id"] for c in overdue]
    assert "conv-overdue" in overdue_ids
    assert "conv-ok" not in overdue_ids

    by_status = client.get("/conversations?sla_status=overdue").json()["conversations"]
    assert all(c["sla_status"] == "overdue" for c in by_status)
    assert any(c["id"] == "conv-overdue" for c in by_status)


def test_auto_assign_by_selected_agent(monkeypatch: pytest.MonkeyPatch) -> None:
    # Configure the assignee map (selected_agent -> assignee id) via the store's settings.
    custom = get_settings().model_copy(
        update={"ticket_default_assignees": {"sales_agent": "alice"}}
    )
    monkeypatch.setattr(store_module, "get_settings", lambda: custom)

    # selected_agent flows from the graph final_state into the record (via _SPRINT2 fields).
    final_state = {**_final_state(), "selected_agent": "sales_agent"}
    with patch("agent_studio.main.graph.ainvoke", new=AsyncMock(return_value=final_state)):
        conv_id = client.post(
            "/webhooks/ghl", json=_ghl_payload(conv_id="conv-auto")
        ).json()["id"]
    record = client.get(f"/conversations/{conv_id}").json()
    assert record["assignee"] == "alice"


def test_auto_assign_unset_leaves_assignee_none(monkeypatch: pytest.MonkeyPatch) -> None:
    # With no map configured, a selected_agent present at creation must NOT auto-assign.
    assert get_settings().ticket_default_assignees is None
    final_state = {**_final_state(), "selected_agent": "sales_agent"}
    with patch("agent_studio.main.graph.ainvoke", new=AsyncMock(return_value=final_state)):
        conv_id = client.post(
            "/webhooks/ghl", json=_ghl_payload(conv_id="conv-noauto")
        ).json()["id"]
    record = client.get(f"/conversations/{conv_id}").json()
    assert record["assignee"] is None


def test_invalid_ticket_status_transition_rejected() -> None:
    conv_id = _create_conversation()
    # open -> resolved is an allowed transition.
    resolved = client.patch(
        f"/conversations/{conv_id}/ticket", json={"ticket_status": "resolved"}
    )
    assert resolved.status_code == 200, resolved.text
    # resolved is terminal: resolved -> open is rejected with 409.
    rejected = client.patch(
        f"/conversations/{conv_id}/ticket", json={"ticket_status": "open"}
    )
    assert rejected.status_code == 409
    # The supervisor force override reopens the resolved ticket.
    forced = client.patch(
        f"/conversations/{conv_id}/ticket?force=true", json={"ticket_status": "open"}
    )
    assert forced.status_code == 200, forced.text
    assert forced.json()["ticket_status"] == "open"