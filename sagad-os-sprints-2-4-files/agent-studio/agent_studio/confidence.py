"""Weighted confidence scoring for Sagad OS.

Final confidence is not a model self-score. It is an operational score built from
retrieval quality, groundedness, policy safety, intent clarity, and tool risk.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

ConfidenceDecision = Literal["auto_send_candidate", "hitl", "hitl_missing_context", "escalate"]


@dataclass(frozen=True)
class ConfidenceBreakdown:
    retrieval_confidence: float
    groundedness_score: float
    policy_safety_score: float
    intent_clarity_score: float
    tool_risk_score: float
    final_score: float
    decision: ConfidenceDecision
    reasons: list[str] = field(default_factory=list)


WEIGHTS = {
    "retrieval_confidence": 0.35,
    "groundedness_score": 0.30,
    "policy_safety_score": 0.20,
    "intent_clarity_score": 0.10,
    "tool_risk_score": 0.05,
}


def clamp_score(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def decide_from_score(
    score: float,
    *,
    risk_level: str,
    missing_knowledge: bool,
    hard_guardrail: bool = False,
) -> ConfidenceDecision:
    if risk_level == "high" or hard_guardrail:
        return "escalate" if score < 0.40 else "hitl"
    if missing_knowledge:
        return "hitl_missing_context" if score >= 0.40 else "escalate"
    if score >= 0.85 and risk_level == "low":
        return "auto_send_candidate"
    if score >= 0.65:
        return "hitl"
    if score >= 0.40:
        return "hitl_missing_context"
    return "escalate"


def calculate_confidence(
    *,
    retrieval_confidence: float,
    groundedness_score: float,
    policy_safety_score: float,
    intent_clarity_score: float,
    tool_risk_score: float,
    risk_level: str,
    missing_knowledge: bool = False,
    hard_guardrail: bool = False,
) -> ConfidenceBreakdown:
    values = {
        "retrieval_confidence": clamp_score(retrieval_confidence),
        "groundedness_score": clamp_score(groundedness_score),
        "policy_safety_score": clamp_score(policy_safety_score),
        "intent_clarity_score": clamp_score(intent_clarity_score),
        "tool_risk_score": clamp_score(tool_risk_score),
    }
    final = round(sum(values[key] * weight for key, weight in WEIGHTS.items()), 4)
    decision = decide_from_score(
        final,
        risk_level=risk_level,
        missing_knowledge=missing_knowledge,
        hard_guardrail=hard_guardrail,
    )
    reasons: list[str] = []
    if missing_knowledge:
        reasons.append("missing approved knowledge")
    if risk_level == "high":
        reasons.append("high-risk conversation forces human review")
    if hard_guardrail:
        reasons.append("hard guardrail fired")
    if final < 0.65:
        reasons.append("final confidence below standard HITL threshold")
    return ConfidenceBreakdown(
        retrieval_confidence=values["retrieval_confidence"],
        groundedness_score=values["groundedness_score"],
        policy_safety_score=values["policy_safety_score"],
        intent_clarity_score=values["intent_clarity_score"],
        tool_risk_score=values["tool_risk_score"],
        final_score=final,
        decision=decision,
        reasons=reasons,
    )
