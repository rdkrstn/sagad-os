"""Lightweight evaluation primitives for Sagad OS Sprint 4."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

EvalDecision = Literal["auto_send_candidate", "hitl", "hitl_missing_context", "escalate", "reject"]


@dataclass(frozen=True)
class EvalCase:
    id: str
    message: str
    expected_intent: str | None = None
    expected_agent: str | None = None
    expected_risk_level: str | None = None
    expected_sources_any: list[str] = field(default_factory=list)
    expected_missing_knowledge: bool | None = None
    expected_decision: EvalDecision | None = None
    blocked_tools: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class EvalPrediction:
    intent: str | None = None
    selected_agent: str | None = None
    risk_level: str | None = None
    source_titles: list[str] = field(default_factory=list)
    source_ids: list[str] = field(default_factory=list)
    missing_knowledge: bool | None = None
    decision: str | None = None
    blocked_tools: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class EvalResult:
    case_id: str
    passed: bool
    score: float
    failures: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class EvalRunSummary:
    total: int
    passed: int
    failed: int
    pass_rate: float
    average_score: float
    failures: dict[str, list[str]] = field(default_factory=dict)


def _matches_any(needles: list[str], values: list[str]) -> bool:
    if not needles:
        return True
    haystack = " ".join(values).lower()
    return any(needle.lower() in haystack for needle in needles)


def evaluate_case(case: EvalCase, prediction: EvalPrediction) -> EvalResult:
    checks = 0
    passed = 0
    failures: list[str] = []

    def check(condition: bool, failure: str) -> None:
        nonlocal checks, passed
        checks += 1
        if condition:
            passed += 1
        else:
            failures.append(failure)

    if case.expected_intent is not None:
        check(prediction.intent == case.expected_intent, f"intent expected {case.expected_intent}, got {prediction.intent}")
    if case.expected_agent is not None:
        check(prediction.selected_agent == case.expected_agent, f"agent expected {case.expected_agent}, got {prediction.selected_agent}")
    if case.expected_risk_level is not None:
        check(prediction.risk_level == case.expected_risk_level, f"risk expected {case.expected_risk_level}, got {prediction.risk_level}")
    if case.expected_sources_any:
        check(
            _matches_any(case.expected_sources_any, prediction.source_titles + prediction.source_ids),
            f"expected one of sources {case.expected_sources_any}",
        )
    if case.expected_missing_knowledge is not None:
        check(
            prediction.missing_knowledge == case.expected_missing_knowledge,
            f"missing_knowledge expected {case.expected_missing_knowledge}, got {prediction.missing_knowledge}",
        )
    if case.expected_decision is not None:
        check(prediction.decision == case.expected_decision, f"decision expected {case.expected_decision}, got {prediction.decision}")
    for tool in case.blocked_tools:
        check(tool in prediction.blocked_tools, f"expected blocked tool: {tool}")

    score = 1.0 if checks == 0 else round(passed / checks, 4)
    return EvalResult(case_id=case.id, passed=not failures, score=score, failures=failures)


def summarize_results(results: list[EvalResult]) -> EvalRunSummary:
    total = len(results)
    passed = sum(1 for result in results if result.passed)
    failed = total - passed
    average_score = 0.0 if total == 0 else round(sum(result.score for result in results) / total, 4)
    failures = {result.case_id: result.failures for result in results if result.failures}
    return EvalRunSummary(
        total=total,
        passed=passed,
        failed=failed,
        pass_rate=0.0 if total == 0 else round(passed / total, 4),
        average_score=average_score,
        failures=failures,
    )
