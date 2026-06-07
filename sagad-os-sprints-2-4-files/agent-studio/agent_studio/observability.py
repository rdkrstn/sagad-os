"""Observability helpers for Sagad OS Sprint 4.

These helpers standardize event names, trace attributes, and redaction without
requiring OpenTelemetry as a hard dependency in the preview runtime.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

EVENTS = {
    "conversation_received": "conversation.received",
    "conversation_ignored": "conversation.ignored",
    "message_normalized": "message.normalized",
    "message_classified": "message.classified",
    "agent_routed": "agent.routed",
    "retrieval_planned": "retrieval.planned",
    "retrieval_completed": "retrieval.completed",
    "retrieval_missing_knowledge": "retrieval.missing_knowledge",
    "tool_planned": "tool.planned",
    "tool_policy_allowed": "tool.policy_allowed",
    "tool_policy_blocked": "tool.policy_blocked",
    "tool_executed": "tool.executed",
    "tool_failed": "tool.failed",
    "draft_generated": "draft.generated",
    "confidence_scored": "confidence.scored",
    "guardrails_applied": "guardrails.applied",
    "approval_created": "approval.created",
    "approval_updated": "approval.updated",
    "delivery_dry_run": "delivery.dry_run",
    "delivery_sent": "delivery.sent",
    "delivery_failed": "delivery.failed",
}

SPAN_NAMES = {
    "normalize": "sagad.graph.normalize",
    "classify": "sagad.graph.classify",
    "route_agent": "sagad.graph.route_agent",
    "retrieve": "sagad.graph.retrieve",
    "plan_tools": "sagad.graph.plan_tools",
    "draft": "sagad.graph.draft",
    "score_confidence": "sagad.graph.score_confidence",
    "apply_guardrails": "sagad.graph.apply_guardrails",
    "decide_delivery": "sagad.graph.decide_delivery",
    "tool_policy": "sagad.tool.policy",
    "tool_execute": "sagad.tool.execute",
    "chatwoot_delivery": "sagad.delivery.chatwoot",
}

SENSITIVE_KEYS = {
    "api_key",
    "api_access_token",
    "authorization",
    "password",
    "secret",
    "token",
    "webhook_token",
    "credit_card",
    "card_number",
}


def event_name(key: str) -> str:
    return EVENTS.get(key, key)


def span_name(key: str) -> str:
    return SPAN_NAMES.get(key, f"sagad.{key}")


def redact_value(key: str, value: Any) -> Any:
    lowered = key.lower()
    if any(sensitive in lowered for sensitive in SENSITIVE_KEYS):
        return "[redacted]"
    if isinstance(value, str) and len(value) > 500:
        return value[:500] + "...[clipped]"
    return value


def redact_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    redacted: dict[str, Any] = {}
    for key, value in payload.items():
        if isinstance(value, Mapping):
            redacted[key] = redact_payload(value)
        elif isinstance(value, list):
            redacted[key] = [redact_payload(item) if isinstance(item, Mapping) else item for item in value[:20]]
        else:
            redacted[key] = redact_value(key, value)
    return redacted


def build_trace_attributes(
    *,
    conversation_id: str | None = None,
    organization_id: str | None = None,
    intent: str | None = None,
    risk_level: str | None = None,
    selected_agent: str | None = None,
    confidence_score: float | None = None,
    delivery_decision: str | None = None,
) -> dict[str, object]:
    attrs: dict[str, object] = {}
    if conversation_id:
        attrs["sagad.conversation_id"] = conversation_id
    if organization_id:
        attrs["sagad.organization_id"] = organization_id
    if intent:
        attrs["sagad.intent"] = intent
    if risk_level:
        attrs["sagad.risk_level"] = risk_level
    if selected_agent:
        attrs["sagad.selected_agent"] = selected_agent
    if confidence_score is not None:
        attrs["sagad.confidence_score"] = round(float(confidence_score), 4)
    if delivery_decision:
        attrs["sagad.delivery_decision"] = delivery_decision
    return attrs
