"""RevOps tiered auto-send safe-lane tests.

Covers `revops_autosend_decision` in isolation and the end-to-end promotion hook in
`_run_universal_inbound` (needs_review -> pass -> auto-send). Uses the test_universal_webhook
harness: mocked `graph.ainvoke`, in-memory store, no credentials. The GHL adapter returns
dry_run in the unconfigured test env, which still counts as a successful auto-send.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from agent_studio.config import Settings, get_settings
from agent_studio.integration_config import integration_config_store
from agent_studio.main import app
from agent_studio.revops_autosend import revops_autosend_decision
from agent_studio.store import store

client = TestClient(app)


def setup_function() -> None:
    store.clear()
    integration_config_store.clear()
    get_settings.cache_clear()


def _settings(**overrides) -> Settings:
    base = dict(
        revops_autosend_enabled=True,
        revops_autosend_intents=["pricing_faq", "business_hours"],
        revops_autosend_confidence=0.88,
    )
    base.update(overrides)
    return Settings(**base)


def _state(*, intent="pricing_faq", risk="low", confidence=0.90, compliance="needs_review", draft="Sure! Oil changes are $39.") -> dict[str, object]:
    return {
        "intent": intent,
        "risk_level": risk,
        "final_confidence_score": confidence,
        "draft_reply": draft,
        "compliance_status": compliance,
    }


# --- revops_autosend_decision (unit) ----------------------------------------

def test_empty_allowlist_never_promotes() -> None:
    settings = _settings(revops_autosend_intents=[])
    assert revops_autosend_decision(_state(), settings) is None


def test_kill_switch_disables_promotion() -> None:
    settings = _settings(revops_autosend_enabled=False)
    assert revops_autosend_decision(_state(), settings) is None


def test_allowlisted_low_risk_high_confidence_promotes() -> None:
    assert revops_autosend_decision(_state(), _settings()) == "pass"


def test_non_allowlisted_intent_not_promoted() -> None:
    assert revops_autosend_decision(_state(intent="commitment_to_purchase"), _settings()) is None


def test_medium_risk_not_promoted() -> None:
    assert revops_autosend_decision(_state(risk="medium"), _settings()) is None


def test_below_threshold_not_promoted() -> None:
    settings = _settings(revops_autosend_confidence=0.95)
    assert revops_autosend_decision(_state(confidence=0.90), settings) is None


def test_empty_draft_not_promoted() -> None:
    assert revops_autosend_decision(_state(draft="   "), _settings()) is None


def test_falls_back_to_retrieval_confidence() -> None:
    state = _state()
    state["final_confidence_score"] = None
    state["retrieval_confidence"] = 0.91
    assert revops_autosend_decision(state, _settings()) == "pass"


# --- end-to-end promotion via POST /webhooks/ghl ----------------------------

def _ghl_payload(*, message_id="msg-as1", conv_id="conv-as") -> dict[str, object]:
    return {
        "type": "InboundMessage",
        "conversationId": conv_id,
        "locationId": "loc-1",
        "message": {"id": message_id, "body": "What are your hours?", "direction": "inbound", "type": "SMS"},
        "contact": {"id": "cont-1", "name": "Jane Doe"},
    }


def _final_state(*, intent="business_hours", risk="low", confidence=0.90, compliance="needs_review", draft="We're open Mon-Fri 8-5.") -> dict[str, object]:
    return {
        "customer_name": "Jane Doe",
        "channel": "sms",
        "incoming_message": "What are your hours?",
        "normalized_message": "hours question",
        "intent": intent,
        "risk_level": risk,
        "retrieved_knowledge": [],
        "draft_reply": draft,
        "qa_findings": [],
        "compliance_status": compliance,
        "retrieval_confidence": confidence,
        "final_confidence_score": confidence,
        "trace_url": None,
    }


def test_default_empty_allowlist_preserves_needs_approval(monkeypatch: pytest.MonkeyPatch) -> None:
    # No REVOPS_AUTOSEND_INTENTS set -> default empty allowlist -> no promotion -> queues.
    monkeypatch.delenv("REVOPS_AUTOSEND_INTENTS", raising=False)
    get_settings.cache_clear()
    with patch("agent_studio.main.graph.ainvoke", new=AsyncMock(return_value=_final_state())):
        response = client.post("/webhooks/ghl", json=_ghl_payload())
    assert response.status_code == 200
    payload = response.json()
    assert payload["compliance_status"] == "needs_review"
    assert payload["approval_status"] == "needs_approval"
    assert payload["send_status"] == "not_sent"


def test_allowlisted_intent_auto_sends_after_promotion(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("REVOPS_AUTOSEND_INTENTS", "business_hours,pricing_faq")
    get_settings.cache_clear()
    # Guardrail said needs_review (not pass); the safe lane promotes it -> auto-send fires.
    with patch("agent_studio.main.graph.ainvoke", new=AsyncMock(return_value=_final_state(compliance="needs_review"))):
        response = client.post("/webhooks/ghl", json=_ghl_payload(message_id="msg-promote"))
    assert response.status_code == 200
    payload = response.json()
    assert payload["compliance_status"] == "pass"
    assert payload["approval_status"] == "sent"
    assert payload["send_status"] == "dry_run"
    assert len(payload["messages"]) == 2  # customer + auto-send ai_agent message
    assert payload["messages"][1]["sender_type"] == "ai_agent"


def test_guardrail_blocked_never_overridden(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("REVOPS_AUTOSEND_INTENTS", "business_hours")
    get_settings.cache_clear()
    # Even though the safe lane would promote, a guardrail "blocked" verdict wins -> no auto-send.
    with patch("agent_studio.main.graph.ainvoke", new=AsyncMock(return_value=_final_state(compliance="blocked"))):
        response = client.post("/webhooks/ghl", json=_ghl_payload(message_id="msg-blocked"))
    assert response.status_code == 200
    payload = response.json()
    assert payload["compliance_status"] == "blocked"
    assert payload["approval_status"] == "needs_approval"
    assert payload["send_status"] == "not_sent"
    assert len(payload["messages"]) == 1


def test_non_allowlisted_intent_queues_even_when_low_risk(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("REVOPS_AUTOSEND_INTENTS", "business_hours")
    get_settings.cache_clear()
    with patch("agent_studio.main.graph.ainvoke", new=AsyncMock(return_value=_final_state(intent="refund_request"))):
        response = client.post("/webhooks/ghl", json=_ghl_payload(message_id="msg-queue"))
    assert response.status_code == 200
    payload = response.json()
    assert payload["compliance_status"] == "needs_review"
    assert payload["approval_status"] == "needs_approval"


def test_higher_confidence_threshold_blocks_auto_send(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("REVOPS_AUTOSEND_INTENTS", "business_hours")
    monkeypatch.setenv("REVOPS_AUTOSEND_CONFIDENCE", "0.95")
    get_settings.cache_clear()
    with patch("agent_studio.main.graph.ainvoke", new=AsyncMock(return_value=_final_state(confidence=0.90))):
        response = client.post("/webhooks/ghl", json=_ghl_payload(message_id="msg-thresh"))
    assert response.status_code == 200
    payload = response.json()
    assert payload["compliance_status"] == "needs_review"
    assert payload["approval_status"] == "needs_approval"