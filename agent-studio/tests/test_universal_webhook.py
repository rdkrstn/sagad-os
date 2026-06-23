"""TestClient tests for the universal webhook (POST /webhooks/{provider}).

Mirrors the existing Chatwoot webhook tests' pattern: `graph.ainvoke` is mocked with an
AsyncMock returning a controlled `final_state`, so these run fast with no credentials and
no GPU. The GHL adapter's own behavior (HMAC/normalize/outbound) is covered by
test_ghl_adapter.py; the DebounceCoordinator by test_debounce.py.
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
    # Each test starts from a clean store + settings cache (same pattern as test_app.py),
    # so conversations don't leak between tests that share a conversation id.
    store.clear()
    integration_config_store.clear()
    get_settings.cache_clear()


def _ghl_payload(*, body: str = "How much does a tune-up cost?", direction: str = "inbound", message_id: str = "msg-1", conv_id: str = "conv-abc") -> dict[str, object]:
    return {
        "type": "InboundMessage",
        "conversationId": conv_id,
        "locationId": "loc-1",
        "message": {"id": message_id, "body": body, "direction": direction, "type": "SMS"},
        "contact": {"id": "cont-1", "name": "Jane Doe"},
    }


def _final_state(*, risk: str = "low", confidence: float = 0.70, compliance: str = "needs_review", draft: str = "Hi Jane! A tune-up is $89. Basis: pricing sheet.") -> dict[str, object]:
    return {
        "customer_name": "Jane Doe",
        "channel": "sms",
        "incoming_message": "How much does a tune-up cost?",
        "normalized_message": "pricing question",
        "intent": "pricing_lead",
        "risk_level": risk,
        "retrieved_knowledge": [],
        "draft_reply": draft,
        "qa_findings": [],
        "compliance_status": compliance,
        "retrieval_confidence": confidence,
        "final_confidence_score": confidence,
        "trace_url": "https://smith.langchain.com/trace/abc",
    }


def test_unknown_provider_returns_404() -> None:
    response = client.post("/webhooks/unknownp", json={"hi": 1})
    assert response.status_code == 404
    assert response.json()["detail"]["error"] == "unknown_webhook_provider"
    assert "ghl" in response.json()["detail"]["known_providers"]


def test_ghl_webhook_creates_conversation() -> None:
    final_state = _final_state()
    with patch("agent_studio.main.graph.ainvoke", new=AsyncMock(return_value=final_state)):
        response = client.post("/webhooks/ghl", json=_ghl_payload())

    assert response.status_code == 200
    payload = response.json()
    assert payload["id"] == "ghl_conv-abc"
    assert payload["customer_name"] == "Jane Doe"
    assert payload["channel"] == "sms"
    assert payload["intent"] == "pricing_lead"
    assert payload["approval_status"] == "needs_approval"
    assert payload["send_status"] == "not_sent"
    assert payload["draft_reply"].startswith("Hi Jane!")
    assert payload["trace_url"] == "https://smith.langchain.com/trace/abc"
    assert payload["messages"][0]["provider"] == "ghl"
    assert payload["messages"][0]["external_message_id"] == "msg-1"


def test_ghl_webhook_auto_sends_low_risk_high_confidence() -> None:
    # GHL unconfigured in test env -> send_outbound returns dry_run, which still counts
    # as a successful auto-send (approval_status="sent", send_status="dry_run").
    final_state = _final_state(compliance="pass", confidence=0.90)
    with patch("agent_studio.main.graph.ainvoke", new=AsyncMock(return_value=final_state)):
        response = client.post("/webhooks/ghl", json=_ghl_payload(message_id="msg-auto"))

    assert response.status_code == 200
    payload = response.json()
    assert payload["approval_status"] == "sent"
    assert payload["send_status"] == "dry_run"
    assert len(payload["messages"]) == 2
    assert payload["messages"][1]["sender_type"] == "ai_agent"
    assert payload["messages"][1]["provider"] == "ghl"


def test_ghl_webhook_high_risk_stays_gated() -> None:
    final_state = _final_state(risk="high", confidence=0.60, compliance="needs_review")
    with patch("agent_studio.main.graph.ainvoke", new=AsyncMock(return_value=final_state)):
        response = client.post("/webhooks/ghl", json=_ghl_payload(message_id="msg-risk"))

    assert response.status_code == 200
    payload = response.json()
    assert payload["risk_level"] == "high"
    assert payload["approval_status"] == "needs_approval"
    assert payload["send_status"] == "not_sent"
    assert len(payload["messages"]) == 1  # no auto-send append


def test_ghl_webhook_ignores_outbound_event() -> None:
    with patch("agent_studio.main.graph.ainvoke", new=AsyncMock(return_value=_final_state())):
        response = client.post("/webhooks/ghl", json=_ghl_payload(direction="outbound"))

    assert response.status_code == 202
    payload = response.json()
    assert payload["status"] == "ignored"


def test_ghl_webhook_missing_content_returns_400() -> None:
    payload = _ghl_payload()
    payload["message"]["body"] = ""
    with patch("agent_studio.main.graph.ainvoke", new=AsyncMock(return_value=_final_state())):
        response = client.post("/webhooks/ghl", json=payload)
    assert response.status_code == 400


def test_ghl_webhook_duplicate_returns_existing() -> None:
    final_state = _final_state()
    with patch("agent_studio.main.graph.ainvoke", new=AsyncMock(return_value=final_state)):
        first = client.post("/webhooks/ghl", json=_ghl_payload(message_id="msg-dup"))
        second = client.post("/webhooks/ghl", json=_ghl_payload(message_id="msg-dup"))

    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json()["id"] == first.json()["id"]
    # The duplicate retry must not append a second customer message.
    assert len(second.json()["messages"]) == 1


def test_ghl_webhook_threads_same_conversation() -> None:
    final_state = _final_state()
    with patch("agent_studio.main.graph.ainvoke", new=AsyncMock(return_value=final_state)):
        first = client.post("/webhooks/ghl", json=_ghl_payload(message_id="m1"))
        second = client.post("/webhooks/ghl", json=_ghl_payload(message_id="m2", body="And booking?"))

    assert second.status_code == 200
    second_payload = second.json()
    assert second_payload["id"] == first.json()["id"]
    assert [m["body"] for m in second_payload["messages"]] == [
        "How much does a tune-up cost?",
        "And booking?",
    ]


class _FakeDebounce:
    """Stand-in for DebounceCoordinator so the 202 path doesn't spawn real background tasks."""

    def __init__(self, debounce_ms: int, process_fn) -> None:
        self.debounce_ms = debounce_ms
        self.process = process_fn
        self.scheduled: list[tuple[str, str]] = []

    async def schedule(self, key, message) -> None:  # type: ignore[no-untyped-def]
        self.scheduled.append((key, message.message_text))

    @property
    def pending_keys(self) -> int:
        return len(self.scheduled)

    async def flush_all(self) -> None:
        self.scheduled.clear()


def test_ghl_webhook_debounced_returns_202(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("WEBHOOK_DEBOUNCE_ENABLED", "true")
    monkeypatch.setenv("WEBHOOK_DEBOUNCE_MS", "2500")
    get_settings.cache_clear()
    # Force a fresh coordinator (FakeDebounce) so no real asyncio task is spawned.
    monkeypatch.setattr("agent_studio.main._debounce", None)

    final_state = _final_state()
    with patch("agent_studio.main.DebounceCoordinator", _FakeDebounce), \
         patch("agent_studio.main.graph.ainvoke", new=AsyncMock(return_value=final_state)):
        response = client.post("/webhooks/ghl", json=_ghl_payload(message_id="msg-deb"))

    assert response.status_code == 202
    payload = response.json()
    assert payload["status"] == "debounced"
    assert payload["provider"] == "ghl"
    assert payload["conversation_id"] == "ghl_conv-abc"
    assert payload["pending_keys"] == 1