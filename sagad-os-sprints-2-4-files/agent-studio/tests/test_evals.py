from agent_studio.evals import EvalCase, EvalPrediction, evaluate_case, summarize_results


def test_eval_case_passes_when_expected_fields_match() -> None:
    case = EvalCase(
        id="refund_001",
        message="I want a refund.",
        expected_intent="refund_or_cancellation",
        expected_agent="support",
        expected_risk_level="high",
        expected_sources_any=["refund"],
        expected_missing_knowledge=False,
        expected_decision="hitl",
    )
    prediction = EvalPrediction(
        intent="refund_or_cancellation",
        selected_agent="support",
        risk_level="high",
        source_titles=["Refund Policy"],
        missing_knowledge=False,
        decision="hitl",
    )
    result = evaluate_case(case, prediction)
    assert result.passed is True
    assert result.score == 1.0


def test_eval_case_reports_failures() -> None:
    case = EvalCase(
        id="shipping_001",
        message="How long is shipping?",
        expected_intent="shipping_question",
        expected_agent="support",
    )
    prediction = EvalPrediction(intent="general_support", selected_agent="sales")
    result = evaluate_case(case, prediction)
    assert result.passed is False
    assert len(result.failures) == 2


def test_eval_summary() -> None:
    results = [
        evaluate_case(EvalCase(id="a", message="x", expected_intent="one"), EvalPrediction(intent="one")),
        evaluate_case(EvalCase(id="b", message="x", expected_intent="two"), EvalPrediction(intent="wrong")),
    ]
    summary = summarize_results(results)
    assert summary.total == 2
    assert summary.passed == 1
    assert summary.failed == 1
    assert summary.pass_rate == 0.5
