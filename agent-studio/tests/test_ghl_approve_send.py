"""GHL manual approve-send (provider dispatch) tests.

`approve_send` now dispatches by provider: a GHL-sourced conversation (provider_conversation_id
set, no Chatwoot context) routes through ``GhlAdapter.send_outbound`` + the
``ghl.messages.send_approved`` tool policy; Chatwoot records keep the existing send path
verbatim. These tests prove the dispatch, the GHL send/audit/broadcast, and that Chatwoot
regression behavior is unchanged.
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


def _ghl_payload(*, conv_id="conv-approve", msg_id="msg-approve") -> dict[str, object]:
    return {
        "type": "InboundMessage",
        "conversationId": conv_id,
        "locationId": "loc-1",
        "message": {"id": msg_id, "body": "Can you confirm my appointment?", "direction": "inbound", "type": "SMS"},
        "contact": {"id": "cont-1", "name": "Jane Doe"},
    }


def _final_state(*, compliance="needs_review") -> dict[str, object]:
    return {
        "customer_name": "Jane Doe",
        "channel": "sms",
        "incoming_message": "Can you confirm my appointment?",
        "normalized_message": "appointment confirmation",
        "intent": "general_support",
        "risk_level": "low",
        "retrieved_knowledge": [],
        "draft_reply": "Your appointment is confirmed for Tuesday at 2pm.",
        "qa_findings": [],
        "compliance_status": compliance,
        "retrieval_confidence": 0.90,
        "final_confidence_score": 0.90,
        "trace_url": None,
    }


def _create_ghl_conversation() -> dict[str, object]:
    """Drive a GHL webhook with a mocked graph so a needs_approval record is persisted."""
    with patch("agent_studio.main.graph.ainvoke", new=AsyncMock(return_value=_final_state())):
        response = client.post("/webhooks/ghl", json=_ghl_payload())
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["approval_status"] == "needs_approval", body
    assert body["provider_conversation_id"] == "conv-approve", body
    return body


def test_ghl_approve_send_dispatches_through_adapter_dry_run() -> None:
    created = _create_ghl_conversation()

    send_mock = AsyncMock(return_value={
        "status": "dry_run",
        "provider": "GHL",
        "action": "ghl.messages.send",
        "detail": "GHL credentials are configured, but dry-run is enabled.",
        "target_url": "https://services.leadconnectorhq.com/conversations/conv-approve/messages",
    })
    with patch("agent_studio.adapters.ghl.GhlAdapter.send_outbound", new=send_mock):
        response = client.post(
            f"/conversations/{created['id']}/approve-send",
            json={"approved": True, "supervisor_id": "qa-lead"},
        )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["approval_status"] == "sent"
    assert payload["send_status"] == "dry_run"
    # The adapter was called with the approved reply + the GHL conversation id.
    send_mock.assert_awaited_once()
    sent_reply = send_mock.await_args.args[0]
    assert "Tuesday at 2pm" in sent_reply
    sent_normalized = send_mock.await_args.args[1]
    assert sent_normalized.provider_conversation_id == "conv-approve"
    # An ai_agent message was appended on the GHL provider, and the tool plan was recorded.
    ai_msgs = [m for m in payload["messages"] if m.get("sender_type") == "ai_agent"]
    assert ai_msgs and ai_msgs[-1].get("provider") == "ghl"
    assert any(p.get("tool_name") == "ghl.messages.send_approved" for p in payload["tool_plans"])
    assert any(p.get("provider") == "GHL" for p in payload["tool_plans"])


def test_ghl_approve_send_live_sent(monkeypatch: pytest.MonkeyPatch) -> None:
    # Configure GHL + turn dry-run off so the policy allows a live send; mock the adapter so we
    # don't hit the real GHL API.
    monkeypatch.setenv("GHL_API_KEY", "key-123")
    monkeypatch.setenv("GHL_LOCATION_ID", "loc-1")
    monkeypatch.setenv("GHL_DRY_RUN", "false")
    get_settings.cache_clear()
    created = _create_ghl_conversation()

    send_mock = AsyncMock(return_value={
        "status": "sent",
        "provider": "GHL",
        "action": "ghl.messages.send",
        "detail": "Approved reply sent to GHL.",
        "target_url": "https://services.leadconnectorhq.com/conversations/conv-approve/messages",
        "http_status": 200,
        "external_id": "out-msg-9",
    })
    with patch("agent_studio.adapters.ghl.GhlAdapter.send_outbound", new=send_mock):
        response = client.post(
            f"/conversations/{created['id']}/approve-send",
            json={"approved": True, "supervisor_id": "qa-lead", "edited_reply": "Edited: Tuesday 2pm confirmed."},
        )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["approval_status"] == "sent"
    assert payload["send_status"] == "sent"
    # Edited reply is what got sent, not the original draft.
    sent_reply = send_mock.await_args.args[0]
    assert sent_reply.startswith("Edited:")
    # The tool result carries the GHL external id.
    assert any(
        r.get("tool_name") == "ghl.messages.send_approved" and r.get("external_id") == "out-msg-9"
        for r in payload["tool_results"]
    )


def test_chatwoot_record_does_not_route_to_ghl_adapter(monkeypatch: pytest.MonkeyPatch) -> None:
    # A Chatwoot conversation must keep using the Chatwoot send path -- the GHL adapter is never
    # called for it. Clear Chatwoot creds so the Chatwoot path dry-runs (mirrors
    # test_approve_send_uses_dry_run_without_chatwoot_credentials). Created via the Chatwoot
    # webhook so chatwoot_conversation_id is set and dispatch stays on the Chatwoot branch.
    monkeypatch.setenv("CHATWOOT_BASE_URL", "")
    monkeypatch.setenv("CHATWOOT_API_ACCESS_TOKEN", "")
    monkeypatch.setenv("CHATWOOT_ACCOUNT_ID", "")
    get_settings.cache_clear()
    created = client.post(
        "/webhooks/chatwoot",
        json={"content": "Hello", "conversation": {"id": 4242}},
    ).json()
    assert created["chatwoot_conversation_id"] is not None

    send_mock = AsyncMock(return_value={"status": "sent", "provider": "GHL", "action": "ghl.messages.send"})
    with patch("agent_studio.adapters.ghl.GhlAdapter.send_outbound", new=send_mock):
        response = client.post(
            f"/conversations/{created['id']}/approve-send",
            json={"approved": True, "supervisor_id": "qa-lead"},
        )

    assert response.status_code == 200, response.text
    payload = response.json()
    # Chatwoot dry-run path still works and the GHL adapter was never consulted.
    assert payload["approval_status"] == "sent"
    assert payload["send_status"] == "dry_run"
    send_mock.assert_not_called()
    assert all(p.get("tool_name") != "ghl.messages.send_approved" for p in payload["tool_plans"])


def test_ghl_approve_send_rejection_does_not_send() -> None:
    created = _create_ghl_conversation()

    send_mock = AsyncMock(return_value={"status": "sent", "provider": "GHL", "action": "ghl.messages.send"})
    with patch("agent_studio.adapters.ghl.GhlAdapter.send_outbound", new=send_mock):
        response = client.post(
            f"/conversations/{created['id']}/approve-send",
            json={"approved": False, "supervisor_id": "qa-lead"},
        )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["approval_status"] == "rejected"
    assert payload["send_status"] == "not_sent"
    send_mock.assert_not_called()