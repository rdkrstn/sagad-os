"""Deterministic guardrails for Sagad OS delivery decisions."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

GuardrailSeverity = Literal["info", "watch", "block"]
DeliveryDecision = Literal["auto_send_candidate", "hitl", "escalate", "reject"]


@dataclass(frozen=True)
class GuardrailFinding:
    code: str
    severity: GuardrailSeverity
    detail: str


@dataclass(frozen=True)
class GuardrailDecision:
    decision: DeliveryDecision
    hard_block: bool
    requires_human: bool
    findings: list[GuardrailFinding] = field(default_factory=list)


LEGAL_TERMS = {"sue", "lawsuit", "lawyer", "attorney", "legal action", "court"}
ANGER_TERMS = {"angry", "furious", "unacceptable", "scam", "fraud", "terrible"}
REFUND_TERMS = {"refund", "money back", "cancel", "cancellation", "chargeback", "compensation"}
PII_TERMS = {"password", "credit card", "card number", "ssn", "social security"}
ACCOUNT_ACTION_TERMS = {"change my email", "update my address", "where is my order", "account", "login"}


def _contains_any(message: str, terms: set[str]) -> bool:
    lower = message.lower()
    return any(term in lower for term in terms)


def assess_guardrails(
    *,
    message: str,
    risk_level: str,
    confidence_score: float,
    missing_knowledge: bool,
    tool_write_planned: bool = False,
    policy_conflict: bool = False,
) -> GuardrailDecision:
    findings: list[GuardrailFinding] = []

    if missing_knowledge:
        findings.append(GuardrailFinding("missing_knowledge", "block", "No sufficient approved source was found."))
    if risk_level == "high":
        findings.append(GuardrailFinding("high_risk", "block", "High-risk cases require human review."))
    if _contains_any(message, LEGAL_TERMS):
        findings.append(GuardrailFinding("legal_threat", "block", "Legal language must be escalated."))
    if _contains_any(message, ANGER_TERMS):
        findings.append(GuardrailFinding("angry_customer", "watch", "Angry customer language requires supervisor review."))
    if _contains_any(message, REFUND_TERMS):
        findings.append(GuardrailFinding("refund_or_compensation", "block", "Refund, cancellation, or compensation language requires HITL."))
    if _contains_any(message, PII_TERMS):
        findings.append(GuardrailFinding("sensitive_information", "block", "Sensitive information request detected."))
    if _contains_any(message, ACCOUNT_ACTION_TERMS):
        findings.append(GuardrailFinding("account_specific", "watch", "Account-specific action or lookup may require verification."))
    if tool_write_planned:
        findings.append(GuardrailFinding("write_tool_planned", "block", "Write tools require approval before execution."))
    if policy_conflict:
        findings.append(GuardrailFinding("policy_conflict", "block", "Policy conflict requires supervisor judgment."))
    if confidence_score < 0.40:
        findings.append(GuardrailFinding("low_confidence", "block", "Confidence is below escalation threshold."))
    elif confidence_score < 0.65:
        findings.append(GuardrailFinding("medium_low_confidence", "watch", "Confidence is below standard HITL threshold."))

    hard_block = any(finding.severity == "block" for finding in findings)
    requires_human = hard_block or any(finding.severity == "watch" for finding in findings)

    if any(finding.code in {"legal_threat", "low_confidence"} for finding in findings):
        decision: DeliveryDecision = "escalate"
    elif requires_human:
        decision = "hitl"
    else:
        decision = "auto_send_candidate"

    return GuardrailDecision(
        decision=decision,
        hard_block=hard_block,
        requires_human=requires_human,
        findings=findings,
    )
