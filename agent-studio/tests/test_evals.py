import pytest

from agent_studio.evals import (
    DEFAULT_EVAL_THRESHOLDS,
    EVAL_DIMENSIONS,
    EvalCase,
    EvalObservation,
    EvalRunThresholdError,
    built_in_eval_cases,
    run_eval_cases,
    run_fixture_evals,
    score_eval_case,
)


def test_built_in_cases_are_stable_and_cover_sprint4_signals() -> None:
    cases = built_in_eval_cases()

    assert [case.id for case in cases] == [
        "classification_refund_high_risk",
        "routing_pricing_sales",
        "retrieval_supported_refund",
        "missing_knowledge_escalates",
        "policy_delivery_approval_gate",
    ]
    assert {dimension for case in cases for dimension in case.dimensions} == set(EVAL_DIMENSIONS)
    assert all(isinstance(case, EvalCase) for case in cases)


def test_score_eval_case_accepts_plain_payload_and_reports_dimension_scores() -> None:
    case = built_in_eval_cases()[0]
    observation = {
        "intent": "refund_or_cancellation",
        "risk_level": "high",
        "selected_agent": "Refund Resolver",
        "retrieval_confidence": 0.71,
        "missing_knowledge": False,
        "retrieved_knowledge": [
            {"title": "Refund Policy", "score": 0.86, "excerpt": "Refunds need review."},
        ],
        "draft_reply": "I can help review the refund request. Basis: Refund Policy.",
        "qa_findings": [{"label": "HITL policy", "status": "pass"}],
        "compliance_status": "needs_review",
        "approval_status": "needs_approval",
        "send_status": "not_sent",
        "tool_plans": [
            {
                "tool_name": "crm.create_note",
                "requires_approval": True,
                "dry_run": True,
                "approved": False,
            },
        ],
        "tool_results": [
            {
                "tool_name": "crm.create_note",
                "status": "blocked",
                "data": {
                    "policy_metadata": {
                        "approval_gate": "supervisor_approval",
                        "requires_approval": True,
                        "approved": False,
                    },
                },
            },
        ],
    }

    result = score_eval_case(case, observation)

    assert result.passed is True
    assert result.score == pytest.approx(1.0)
    assert {score.dimension for score in result.scores} == set(case.dimensions)
    assert all(score.passed for score in result.scores)


def test_scoring_catches_missing_knowledge_and_guardrail_failures() -> None:
    case = next(case for case in built_in_eval_cases() if case.id == "missing_knowledge_escalates")
    result = score_eval_case(
        case,
        EvalObservation(
            intent="general_support",
            risk_level="medium",
            selected_agent="general_support",
            retrieval_confidence=0.78,
            missing_knowledge=False,
            retrieved_knowledge=[{"title": "General FAQ", "score": 0.2}],
            draft_reply="Yes, we can definitely support warranty coverage for that custom contract.",
            qa_findings=[{"label": "Knowledge basis", "status": "pass"}],
            compliance_status="pass",
            approval_status="needs_approval",
            send_status="not_sent",
            tool_plans=[],
            tool_results=[],
        ),
    )

    assert result.passed is False
    failed = {score.dimension: score.detail for score in result.scores if not score.passed}
    assert failed["missing_knowledge"] == "expected missing_knowledge=True, observed False"
    assert "insufficient-source language" in failed["draft"]
    assert "watch or fail finding" in failed["guardrail"]


def test_run_fixture_evals_passes_default_thresholds_without_provider_calls() -> None:
    summary = run_fixture_evals()

    assert summary.case_count == 5
    assert summary.passed_case_count == 5
    assert summary.failed_case_count == 0
    assert summary.overall_score == pytest.approx(1.0)
    assert all(check.passed for check in summary.threshold_checks)


def test_run_eval_cases_returns_threshold_failures_and_can_raise() -> None:
    case = next(case for case in built_in_eval_cases() if case.id == "routing_pricing_sales")
    bad_observation = EvalObservation(
        intent="pricing_lead",
        risk_level="low",
        selected_agent="general_support",
        retrieval_confidence=0.2,
        missing_knowledge=True,
        retrieved_knowledge=[],
        draft_reply="Can you share more detail?",
        qa_findings=[],
        compliance_status="needs_review",
        approval_status="needs_approval",
        send_status="not_sent",
        tool_plans=[],
        tool_results=[],
    )

    summary = run_eval_cases([case], {case.id: bad_observation}, thresholds=DEFAULT_EVAL_THRESHOLDS)

    assert summary.passed is False
    assert summary.failed_case_ids == [case.id]
    assert any(check.dimension == "routing" and not check.passed for check in summary.threshold_checks)
    with pytest.raises(EvalRunThresholdError):
        summary.raise_for_thresholds()
