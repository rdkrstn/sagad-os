"""Deterministic Sprint 4 evaluation helpers for Agent Studio.

The eval layer is intentionally provider-free. Integrators can pass a
``ConversationRecord``-like object, a Pydantic model, or a plain dict captured
after the graph/store layer finishes a conversation turn.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from statistics import mean
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


EvalDimension = Literal[
    "classification",
    "routing",
    "retrieval",
    "missing_knowledge",
    "draft",
    "guardrail",
    "tool_policy",
    "delivery",
]

EVAL_DIMENSIONS: tuple[EvalDimension, ...] = (
    "classification",
    "routing",
    "retrieval",
    "missing_knowledge",
    "draft",
    "guardrail",
    "tool_policy",
    "delivery",
)

DEFAULT_EVAL_THRESHOLDS: dict[str, float] = {
    "overall": 1.0,
    **{dimension: 1.0 for dimension in EVAL_DIMENSIONS},
}


class EvalDeliveryExpectation(BaseModel):
    model_config = ConfigDict(frozen=True)

    approval_status: str | None = "needs_approval"
    send_status: str | None = "not_sent"
    require_not_sent: bool = True


class EvalToolPolicyExpectation(BaseModel):
    model_config = ConfigDict(frozen=True)

    min_tool_plans: int = 0
    min_tool_results: int = 0
    expected_tool_names: tuple[str, ...] = ()
    require_supervisor_approval_gate: bool = False
    require_dry_run: bool | None = None
    allowed_result_statuses: tuple[str, ...] = ()


class EvalExpectation(BaseModel):
    model_config = ConfigDict(frozen=True)

    intent: str | None = None
    risk_level: str | None = None
    selected_agent: str | None = None
    min_retrieval_confidence: float | None = None
    max_retrieval_confidence: float | None = None
    min_knowledge_hits: int = 0
    required_knowledge_titles: tuple[str, ...] = ()
    missing_knowledge: bool | None = None
    required_draft_terms: tuple[str, ...] = ()
    forbidden_draft_terms: tuple[str, ...] = ()
    require_citation: bool = False
    require_insufficient_source_language: bool = False
    required_guardrail_labels: tuple[str, ...] = ()
    guardrail_watch_or_fail_labels: tuple[str, ...] = ()
    compliance_status: str | None = None
    tool_policy: EvalToolPolicyExpectation = Field(default_factory=EvalToolPolicyExpectation)
    delivery: EvalDeliveryExpectation = Field(default_factory=EvalDeliveryExpectation)


class EvalObservation(BaseModel):
    model_config = ConfigDict(extra="allow")

    intent: str | None = None
    risk_level: str | None = None
    selected_agent: str | None = None
    retrieval_confidence: float | None = None
    missing_knowledge: bool | None = None
    retrieved_knowledge: list[dict[str, Any]] = Field(default_factory=list)
    draft_reply: str = ""
    qa_findings: list[dict[str, Any]] = Field(default_factory=list)
    compliance_status: str | None = None
    approval_status: str | None = None
    send_status: str | None = None
    tool_plans: list[dict[str, Any]] = Field(default_factory=list)
    tool_results: list[dict[str, Any]] = Field(default_factory=list)

    @field_validator("retrieved_knowledge", "qa_findings", "tool_plans", "tool_results", mode="before")
    @classmethod
    def _coerce_model_items(cls, value: Any) -> list[dict[str, Any]]:
        if value is None:
            return []
        if not isinstance(value, Sequence) or isinstance(value, str | bytes):
            return []
        return [_object_to_mapping(item) for item in value]


class EvalCase(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    name: str
    incoming_message: str
    dimensions: tuple[EvalDimension, ...]
    expectation: EvalExpectation
    description: str = ""
    fixture_observation: EvalObservation | None = None

    @field_validator("dimensions")
    @classmethod
    def _dimensions_must_be_known(
        cls,
        value: tuple[EvalDimension, ...],
    ) -> tuple[EvalDimension, ...]:
        if not value:
            raise ValueError("EvalCase.dimensions must not be empty.")
        unknown = sorted(set(value).difference(EVAL_DIMENSIONS))
        if unknown:
            raise ValueError(f"Unknown eval dimensions: {unknown}")
        return value


class EvalDimensionScore(BaseModel):
    dimension: EvalDimension
    passed: bool
    score: float
    detail: str
    observed: dict[str, Any] = Field(default_factory=dict)
    expected: dict[str, Any] = Field(default_factory=dict)


class EvalCaseResult(BaseModel):
    case_id: str
    name: str
    passed: bool
    score: float
    scores: list[EvalDimensionScore]


class EvalThresholdCheck(BaseModel):
    dimension: str
    score: float
    threshold: float
    passed: bool


class EvalRunThresholdError(RuntimeError):
    """Raised when an eval summary does not satisfy configured thresholds."""


class EvalRunSummary(BaseModel):
    run_id: str
    case_count: int
    passed_case_count: int
    failed_case_count: int
    failed_case_ids: list[str]
    overall_score: float
    dimension_scores: dict[str, float]
    threshold_checks: list[EvalThresholdCheck]
    passed: bool
    results: list[EvalCaseResult]

    def raise_for_thresholds(self) -> None:
        failed = [check for check in self.threshold_checks if not check.passed]
        if not failed:
            return
        detail = "; ".join(
            f"{check.dimension}={check.score:.2f} below {check.threshold:.2f}"
            for check in failed
        )
        raise EvalRunThresholdError(detail)


def built_in_eval_cases() -> list[EvalCase]:
    """Return deterministic fixture cases for Sprint 4 signal coverage."""

    return [
        EvalCase(
            id="classification_refund_high_risk",
            name="Refund request is classified high risk and supervisor-gated",
            incoming_message="I want to cancel this order and get my money back.",
            dimensions=(
                "classification",
                "routing",
                "retrieval",
                "missing_knowledge",
                "draft",
                "guardrail",
                "tool_policy",
                "delivery",
            ),
            expectation=EvalExpectation(
                intent="refund_or_cancellation",
                risk_level="high",
                selected_agent="refund_resolver",
                min_retrieval_confidence=0.6,
                min_knowledge_hits=1,
                required_knowledge_titles=("refund",),
                missing_knowledge=False,
                required_draft_terms=("refund", "Basis:"),
                forbidden_draft_terms=("guaranteed refund", "definitely refund"),
                require_citation=True,
                required_guardrail_labels=("HITL policy",),
                compliance_status="needs_review",
                tool_policy=EvalToolPolicyExpectation(
                    min_tool_plans=1,
                    min_tool_results=1,
                    expected_tool_names=("crm.create_note",),
                    require_supervisor_approval_gate=True,
                    require_dry_run=True,
                    allowed_result_statuses=("blocked", "dry_run"),
                ),
                delivery=EvalDeliveryExpectation(),
            ),
            fixture_observation=EvalObservation(
                intent="refund_or_cancellation",
                risk_level="high",
                selected_agent="refund_resolver",
                retrieval_confidence=0.82,
                missing_knowledge=False,
                retrieved_knowledge=[
                    {
                        "title": "Refund Policy",
                        "score": 0.88,
                        "excerpt": "Refund requests require supervisor review.",
                    },
                ],
                draft_reply=(
                    "I can help review the refund request, but a supervisor must approve "
                    "any outcome. Basis: Refund Policy."
                ),
                qa_findings=[
                    {"label": "HITL policy", "status": "pass"},
                    {"label": "High-risk escalation", "status": "watch"},
                ],
                compliance_status="needs_review",
                approval_status="needs_approval",
                send_status="not_sent",
                tool_plans=[
                    {
                        "tool_name": "crm.create_note",
                        "requires_approval": True,
                        "approved": False,
                        "dry_run": True,
                    },
                ],
                tool_results=[
                    {
                        "tool_name": "crm.create_note",
                        "status": "blocked",
                        "data": {
                            "policy_metadata": {
                                "approval_gate": "supervisor_approval",
                                "requires_approval": True,
                                "approved": False,
                            },
                            "policy_decision": {"dry_run": True},
                        },
                    },
                ],
            ),
        ),
        EvalCase(
            id="routing_pricing_sales",
            name="Pricing lead routes to sales with source-backed draft",
            incoming_message="Can you quote the monthly cost for a five-seat team?",
            dimensions=("classification", "routing", "retrieval", "draft", "guardrail", "delivery"),
            expectation=EvalExpectation(
                intent="pricing_lead",
                risk_level="low",
                selected_agent="sales_agent",
                min_retrieval_confidence=0.5,
                min_knowledge_hits=1,
                required_knowledge_titles=("pricing",),
                missing_knowledge=False,
                required_draft_terms=("pricing", "team", "Basis:"),
                forbidden_draft_terms=("guaranteed discount",),
                require_citation=True,
                required_guardrail_labels=("Knowledge basis", "HITL policy"),
                compliance_status="needs_review",
                delivery=EvalDeliveryExpectation(),
            ),
            fixture_observation=EvalObservation(
                intent="pricing_lead",
                risk_level="low",
                selected_agent="sales_agent",
                retrieval_confidence=0.76,
                missing_knowledge=False,
                retrieved_knowledge=[
                    {
                        "title": "Pricing Qualification SOP",
                        "score": 0.8,
                        "excerpt": "Ask for seats, timeline, and product fit before quoting.",
                    },
                ],
                draft_reply=(
                    "I can help with pricing for a five-seat team. What timeline are you "
                    "planning around? Basis: Pricing Qualification SOP."
                ),
                qa_findings=[
                    {"label": "Knowledge basis", "status": "pass"},
                    {"label": "HITL policy", "status": "pass"},
                ],
                compliance_status="needs_review",
                approval_status="needs_approval",
                send_status="not_sent",
            ),
        ),
        EvalCase(
            id="retrieval_supported_refund",
            name="Refund answer has enough approved retrieval coverage",
            incoming_message="What is your cancellation and refund process?",
            dimensions=("retrieval", "missing_knowledge", "draft", "guardrail", "delivery"),
            expectation=EvalExpectation(
                min_retrieval_confidence=0.7,
                min_knowledge_hits=2,
                required_knowledge_titles=("refund", "cancellation"),
                missing_knowledge=False,
                required_draft_terms=("refund", "cancellation", "Basis:"),
                forbidden_draft_terms=("instant refund",),
                require_citation=True,
                required_guardrail_labels=("Knowledge basis",),
                compliance_status="needs_review",
                delivery=EvalDeliveryExpectation(),
            ),
            fixture_observation=EvalObservation(
                intent="refund_or_cancellation",
                risk_level="high",
                selected_agent="refund_resolver",
                retrieval_confidence=0.87,
                missing_knowledge=False,
                retrieved_knowledge=[
                    {
                        "title": "Refund Policy",
                        "score": 0.9,
                        "excerpt": "Refunds require eligibility review.",
                    },
                    {
                        "title": "Cancellation SOP",
                        "score": 0.83,
                        "excerpt": "Cancellations need order verification.",
                    },
                ],
                draft_reply=(
                    "The refund and cancellation process starts with verification, then "
                    "supervisor review for the final outcome. Basis: Refund Policy, "
                    "Cancellation SOP."
                ),
                qa_findings=[{"label": "Knowledge basis", "status": "pass"}],
                compliance_status="needs_review",
                approval_status="needs_approval",
                send_status="not_sent",
            ),
        ),
        EvalCase(
            id="missing_knowledge_escalates",
            name="Unknown edge case is marked missing knowledge and escalated",
            incoming_message="Does my custom enterprise warranty cover a one-off import?",
            dimensions=(
                "retrieval",
                "missing_knowledge",
                "draft",
                "guardrail",
                "delivery",
            ),
            expectation=EvalExpectation(
                max_retrieval_confidence=0.39,
                min_knowledge_hits=0,
                missing_knowledge=True,
                required_draft_terms=("supervisor",),
                forbidden_draft_terms=("definitely support", "guaranteed", "covered"),
                require_insufficient_source_language=True,
                required_guardrail_labels=("Missing knowledge",),
                guardrail_watch_or_fail_labels=("Missing knowledge",),
                compliance_status="needs_review",
                delivery=EvalDeliveryExpectation(),
            ),
            fixture_observation=EvalObservation(
                intent="general_support",
                risk_level="medium",
                selected_agent="general_support",
                retrieval_confidence=0.0,
                missing_knowledge=True,
                retrieved_knowledge=[],
                draft_reply=(
                    "I do not have enough approved source material to confirm that warranty "
                    "edge case. A supervisor should review it before we give an answer."
                ),
                qa_findings=[{"label": "Missing knowledge", "status": "watch"}],
                compliance_status="needs_review",
                approval_status="needs_approval",
                send_status="not_sent",
            ),
        ),
        EvalCase(
            id="policy_delivery_approval_gate",
            name="Tool policy and delivery stay behind supervisor approval",
            incoming_message="Please send the customer the approved reply.",
            dimensions=("tool_policy", "delivery", "guardrail"),
            expectation=EvalExpectation(
                required_guardrail_labels=("HITL policy",),
                compliance_status="needs_review",
                tool_policy=EvalToolPolicyExpectation(
                    min_tool_plans=1,
                    min_tool_results=1,
                    expected_tool_names=("chatwoot.messages.send_approved",),
                    require_supervisor_approval_gate=True,
                    require_dry_run=True,
                    allowed_result_statuses=("blocked", "dry_run"),
                ),
                delivery=EvalDeliveryExpectation(
                    approval_status="needs_approval",
                    send_status="not_sent",
                    require_not_sent=True,
                ),
            ),
            fixture_observation=EvalObservation(
                intent="general_support",
                risk_level="medium",
                selected_agent="general_support",
                retrieval_confidence=0.5,
                missing_knowledge=False,
                draft_reply="Draft remains queued for supervisor approval.",
                qa_findings=[{"label": "HITL policy", "status": "pass"}],
                compliance_status="needs_review",
                approval_status="needs_approval",
                send_status="not_sent",
                tool_plans=[
                    {
                        "tool_name": "chatwoot.messages.send_approved",
                        "requires_approval": True,
                        "approved": False,
                        "dry_run": True,
                    },
                ],
                tool_results=[
                    {
                        "tool_name": "chatwoot.messages.send_approved",
                        "status": "blocked",
                        "data": {
                            "policy_metadata": {
                                "approval_gate": "supervisor_approval",
                                "requires_approval": True,
                                "approved": False,
                            },
                            "policy_decision": {"dry_run": True},
                        },
                    },
                ],
            ),
        ),
    ]


def run_fixture_evals(
    *,
    thresholds: Mapping[str, float] | None = None,
    run_id: str = "builtin-fixture",
) -> EvalRunSummary:
    cases = built_in_eval_cases()
    observations = {
        case.id: case.fixture_observation
        for case in cases
        if case.fixture_observation is not None
    }
    return run_eval_cases(cases, observations, thresholds=thresholds, run_id=run_id)


def run_eval_cases(
    cases: Sequence[EvalCase],
    observations: Mapping[str, EvalObservation | Mapping[str, Any] | Any],
    *,
    thresholds: Mapping[str, float] | None = None,
    run_id: str = "eval-run",
) -> EvalRunSummary:
    results = [
        score_eval_case(case, observations.get(case.id) or case.fixture_observation)
        for case in cases
    ]
    dimension_scores = _aggregate_dimension_scores(results)
    overall_score = _round_score(mean([result.score for result in results]) if results else 0.0)
    failed_case_ids = [result.case_id for result in results if not result.passed]
    checks = _threshold_checks(
        overall_score=overall_score,
        dimension_scores=dimension_scores,
        thresholds=thresholds or DEFAULT_EVAL_THRESHOLDS,
    )
    passed = not failed_case_ids and all(check.passed for check in checks)
    return EvalRunSummary(
        run_id=run_id,
        case_count=len(results),
        passed_case_count=len(results) - len(failed_case_ids),
        failed_case_count=len(failed_case_ids),
        failed_case_ids=failed_case_ids,
        overall_score=overall_score,
        dimension_scores=dimension_scores,
        threshold_checks=checks,
        passed=passed,
        results=results,
    )


def score_eval_case(
    case: EvalCase,
    observation: EvalObservation | Mapping[str, Any] | Any,
) -> EvalCaseResult:
    observed = _coerce_observation(observation)
    scores = [
        _score_dimension(dimension, case.expectation, observed)
        for dimension in case.dimensions
    ]
    case_score = _round_score(mean([score.score for score in scores]) if scores else 0.0)
    return EvalCaseResult(
        case_id=case.id,
        name=case.name,
        passed=all(score.passed for score in scores),
        score=case_score,
        scores=scores,
    )


def _score_dimension(
    dimension: EvalDimension,
    expected: EvalExpectation,
    observed: EvalObservation,
) -> EvalDimensionScore:
    if dimension == "classification":
        return _score_classification(expected, observed)
    if dimension == "routing":
        return _score_routing(expected, observed)
    if dimension == "retrieval":
        return _score_retrieval(expected, observed)
    if dimension == "missing_knowledge":
        return _score_missing_knowledge(expected, observed)
    if dimension == "draft":
        return _score_draft(expected, observed)
    if dimension == "guardrail":
        return _score_guardrail(expected, observed)
    if dimension == "tool_policy":
        return _score_tool_policy(expected, observed)
    if dimension == "delivery":
        return _score_delivery(expected, observed)
    raise ValueError(f"Unsupported eval dimension: {dimension}")


def _score_classification(
    expected: EvalExpectation,
    observed: EvalObservation,
) -> EvalDimensionScore:
    if expected.intent and observed.intent != expected.intent:
        return _fail(
            "classification",
            f"expected intent={expected.intent}, observed {observed.intent}",
            {"intent": observed.intent},
            {"intent": expected.intent},
        )
    if expected.risk_level and observed.risk_level != expected.risk_level:
        return _fail(
            "classification",
            f"expected risk_level={expected.risk_level}, observed {observed.risk_level}",
            {"risk_level": observed.risk_level},
            {"risk_level": expected.risk_level},
        )
    return _pass("classification", "classification matched expected intent and risk")


def _score_routing(expected: EvalExpectation, observed: EvalObservation) -> EvalDimensionScore:
    if expected.selected_agent and _normalize_name(observed.selected_agent) != _normalize_name(
        expected.selected_agent
    ):
        return _fail(
            "routing",
            f"expected selected_agent={expected.selected_agent}, observed {observed.selected_agent}",
            {"selected_agent": observed.selected_agent},
            {"selected_agent": expected.selected_agent},
        )
    return _pass("routing", "routing matched expected selected agent")


def _score_retrieval(
    expected: EvalExpectation,
    observed: EvalObservation,
) -> EvalDimensionScore:
    failures: list[str] = []
    confidence = observed.retrieval_confidence
    hit_count = len(observed.retrieved_knowledge)

    if expected.min_retrieval_confidence is not None:
        if confidence is None or confidence < expected.min_retrieval_confidence:
            failures.append(
                "expected retrieval_confidence >= "
                f"{expected.min_retrieval_confidence:.2f}, observed {_format_score(confidence)}"
            )
    if expected.max_retrieval_confidence is not None:
        if confidence is None or confidence > expected.max_retrieval_confidence:
            failures.append(
                "expected retrieval_confidence <= "
                f"{expected.max_retrieval_confidence:.2f}, observed {_format_score(confidence)}"
            )
    if hit_count < expected.min_knowledge_hits:
        failures.append(
            f"expected at least {expected.min_knowledge_hits} knowledge hit(s), observed {hit_count}"
        )
    missing_titles = [
        title
        for title in expected.required_knowledge_titles
        if not _knowledge_title_present(title, observed.retrieved_knowledge)
    ]
    if missing_titles:
        failures.append(f"missing knowledge title terms: {', '.join(missing_titles)}")
    if failures:
        return _fail(
            "retrieval",
            "; ".join(failures),
            {
                "retrieval_confidence": confidence,
                "knowledge_hit_count": hit_count,
            },
            {
                "min_retrieval_confidence": expected.min_retrieval_confidence,
                "max_retrieval_confidence": expected.max_retrieval_confidence,
                "min_knowledge_hits": expected.min_knowledge_hits,
                "required_knowledge_titles": list(expected.required_knowledge_titles),
            },
        )
    return _pass("retrieval", "retrieval matched expected confidence and source coverage")


def _score_missing_knowledge(
    expected: EvalExpectation,
    observed: EvalObservation,
) -> EvalDimensionScore:
    if expected.missing_knowledge is not None and observed.missing_knowledge != expected.missing_knowledge:
        return _fail(
            "missing_knowledge",
            f"expected missing_knowledge={expected.missing_knowledge}, observed {observed.missing_knowledge}",
            {"missing_knowledge": observed.missing_knowledge},
            {"missing_knowledge": expected.missing_knowledge},
        )
    return _pass("missing_knowledge", "missing knowledge signal matched expectation")


def _score_draft(expected: EvalExpectation, observed: EvalObservation) -> EvalDimensionScore:
    draft = observed.draft_reply or ""
    lowered = draft.lower()
    if expected.require_insufficient_source_language and not _has_insufficient_source_language(draft):
        return _fail(
            "draft",
            "draft missing insufficient-source language",
            {"draft_reply": draft},
            {"require_insufficient_source_language": True},
        )
    missing_terms = [term for term in expected.required_draft_terms if term.lower() not in lowered]
    if missing_terms:
        return _fail(
            "draft",
            f"draft missing required terms: {', '.join(missing_terms)}",
            {"draft_reply": draft},
            {"required_draft_terms": list(expected.required_draft_terms)},
        )
    forbidden_terms = [term for term in expected.forbidden_draft_terms if term.lower() in lowered]
    if forbidden_terms:
        return _fail(
            "draft",
            f"draft included forbidden terms: {', '.join(forbidden_terms)}",
            {"draft_reply": draft},
            {"forbidden_draft_terms": list(expected.forbidden_draft_terms)},
        )
    if expected.require_citation and not _has_citation_signal(draft, observed.retrieved_knowledge):
        return _fail(
            "draft",
            "draft missing citation or source basis",
            {"draft_reply": draft},
            {"require_citation": True},
        )
    return _pass("draft", "draft matched expected grounding and safety language")


def _score_guardrail(
    expected: EvalExpectation,
    observed: EvalObservation,
) -> EvalDimensionScore:
    findings = _findings_by_label(observed.qa_findings)
    for label in expected.guardrail_watch_or_fail_labels:
        finding = findings.get(_normalize_name(label))
        status = _field_value(finding or {}, "status")
        if str(status).lower() not in {"watch", "fail"}:
            return _fail(
                "guardrail",
                f"expected watch or fail finding for {label}, observed {status or 'missing'}",
                {"qa_findings": observed.qa_findings},
                {"guardrail_watch_or_fail_labels": list(expected.guardrail_watch_or_fail_labels)},
            )
    missing_labels = [
        label
        for label in expected.required_guardrail_labels
        if _normalize_name(label) not in findings
    ]
    if missing_labels:
        return _fail(
            "guardrail",
            f"missing guardrail finding: {', '.join(missing_labels)}",
            {"qa_findings": observed.qa_findings},
            {"required_guardrail_labels": list(expected.required_guardrail_labels)},
        )
    if expected.compliance_status and observed.compliance_status != expected.compliance_status:
        return _fail(
            "guardrail",
            f"expected compliance_status={expected.compliance_status}, observed {observed.compliance_status}",
            {"compliance_status": observed.compliance_status},
            {"compliance_status": expected.compliance_status},
        )
    return _pass("guardrail", "guardrail findings matched expected policy posture")


def _score_tool_policy(
    expected: EvalExpectation,
    observed: EvalObservation,
) -> EvalDimensionScore:
    policy = expected.tool_policy
    plans = observed.tool_plans
    results = observed.tool_results
    failures: list[str] = []

    if len(plans) < policy.min_tool_plans:
        failures.append(f"expected at least {policy.min_tool_plans} tool plan(s), observed {len(plans)}")
    if len(results) < policy.min_tool_results:
        failures.append(
            f"expected at least {policy.min_tool_results} tool result(s), observed {len(results)}"
        )
    if policy.expected_tool_names:
        observed_names = {_field_value(item, "tool_name") for item in [*plans, *results]}
        missing_names = [
            name
            for name in policy.expected_tool_names
            if name not in observed_names
        ]
        if missing_names:
            failures.append(f"missing tool policy names: {', '.join(missing_names)}")
    if policy.require_supervisor_approval_gate and not _has_supervisor_approval_gate(plans, results):
        failures.append("missing supervisor approval gate")
    if policy.require_dry_run is not None and _has_dry_run(plans, results) is not policy.require_dry_run:
        failures.append(f"expected dry_run={policy.require_dry_run}")
    if policy.allowed_result_statuses:
        outside_statuses = [
            str(_field_value(result, "status"))
            for result in results
            if str(_field_value(result, "status")) not in policy.allowed_result_statuses
        ]
        if outside_statuses:
            failures.append(f"unexpected tool result statuses: {', '.join(outside_statuses)}")
    if failures:
        return _fail(
            "tool_policy",
            "; ".join(failures),
            {"tool_plans": plans, "tool_results": results},
            policy.model_dump(),
        )
    return _pass("tool_policy", "tool policy matched approval and dry-run expectations")


def _score_delivery(
    expected: EvalExpectation,
    observed: EvalObservation,
) -> EvalDimensionScore:
    delivery = expected.delivery
    if delivery.approval_status and observed.approval_status != delivery.approval_status:
        return _fail(
            "delivery",
            f"expected approval_status={delivery.approval_status}, observed {observed.approval_status}",
            {"approval_status": observed.approval_status},
            {"approval_status": delivery.approval_status},
        )
    if delivery.send_status and observed.send_status != delivery.send_status:
        return _fail(
            "delivery",
            f"expected send_status={delivery.send_status}, observed {observed.send_status}",
            {"send_status": observed.send_status},
            {"send_status": delivery.send_status},
        )
    if delivery.require_not_sent and str(observed.send_status).lower() in {"sent", "succeeded"}:
        return _fail(
            "delivery",
            f"expected delivery to remain unsent, observed send_status={observed.send_status}",
            {"send_status": observed.send_status},
            {"require_not_sent": True},
        )
    return _pass("delivery", "delivery remained behind the expected approval state")


def _threshold_checks(
    *,
    overall_score: float,
    dimension_scores: Mapping[str, float],
    thresholds: Mapping[str, float],
) -> list[EvalThresholdCheck]:
    checks: list[EvalThresholdCheck] = []
    for dimension, threshold in thresholds.items():
        if dimension == "overall":
            score = overall_score
        elif dimension in dimension_scores:
            score = dimension_scores[dimension]
        else:
            continue
        checks.append(
            EvalThresholdCheck(
                dimension=dimension,
                score=score,
                threshold=float(threshold),
                passed=score >= float(threshold),
            )
        )
    return checks


def _aggregate_dimension_scores(results: Sequence[EvalCaseResult]) -> dict[str, float]:
    grouped: dict[str, list[float]] = {}
    for result in results:
        for score in result.scores:
            grouped.setdefault(score.dimension, []).append(score.score)
    return {
        dimension: _round_score(mean(scores))
        for dimension, scores in grouped.items()
        if scores
    }


def _coerce_observation(observation: EvalObservation | Mapping[str, Any] | Any) -> EvalObservation:
    if observation is None:
        return EvalObservation()
    if isinstance(observation, EvalObservation):
        return observation
    if isinstance(observation, BaseModel):
        return EvalObservation.model_validate(observation.model_dump())
    if isinstance(observation, Mapping):
        return EvalObservation.model_validate(dict(observation))
    return EvalObservation.model_validate(_object_to_mapping(observation))


def _object_to_mapping(value: Any) -> dict[str, Any]:
    if isinstance(value, BaseModel):
        return value.model_dump()
    if isinstance(value, Mapping):
        return dict(value)
    if hasattr(value, "__dict__"):
        return {
            key: item
            for key, item in vars(value).items()
            if not key.startswith("_")
        }
    return {}


def _pass(dimension: EvalDimension, detail: str) -> EvalDimensionScore:
    return EvalDimensionScore(
        dimension=dimension,
        passed=True,
        score=1.0,
        detail=detail,
    )


def _fail(
    dimension: EvalDimension,
    detail: str,
    observed: Mapping[str, Any],
    expected: Mapping[str, Any],
) -> EvalDimensionScore:
    return EvalDimensionScore(
        dimension=dimension,
        passed=False,
        score=0.0,
        detail=detail,
        observed=dict(observed),
        expected=dict(expected),
    )


def _normalize_name(value: Any) -> str:
    return "".join(char for char in str(value or "").lower() if char.isalnum())


def _knowledge_title_present(term: str, hits: Sequence[Mapping[str, Any]]) -> bool:
    expected = term.lower()
    for hit in hits:
        haystack = " ".join(
            str(_field_value(hit, field) or "").lower()
            for field in ("title", "category", "source_path", "excerpt")
        )
        if expected in haystack:
            return True
    return False


def _has_citation_signal(draft: str, hits: Sequence[Mapping[str, Any]]) -> bool:
    lowered = draft.lower()
    if "basis:" in lowered or "source" in lowered:
        return True
    return any(
        str(_field_value(hit, "title") or "").lower() in lowered
        for hit in hits
        if _field_value(hit, "title")
    )


def _has_insufficient_source_language(draft: str) -> bool:
    lowered = draft.lower()
    source_signals = ("source", "approved", "policy", "knowledge", "material")
    uncertainty_signals = ("not enough", "insufficient", "cannot confirm", "do not have enough")
    escalation_signals = ("supervisor", "review", "more context")
    return (
        any(signal in lowered for signal in source_signals)
        and any(signal in lowered for signal in uncertainty_signals)
        and any(signal in lowered for signal in escalation_signals)
    )


def _findings_by_label(findings: Sequence[Mapping[str, Any]]) -> dict[str, Mapping[str, Any]]:
    return {
        _normalize_name(_field_value(finding, "label")): finding
        for finding in findings
        if _field_value(finding, "label")
    }


def _has_supervisor_approval_gate(
    plans: Sequence[Mapping[str, Any]],
    results: Sequence[Mapping[str, Any]],
) -> bool:
    if any(bool(_field_value(plan, "requires_approval")) for plan in plans):
        return True
    for result in results:
        metadata = _nested_mapping(result, ("data", "policy_metadata"))
        if _field_value(metadata, "approval_gate") == "supervisor_approval":
            return True
        if bool(_field_value(metadata, "requires_approval")):
            return True
    return False


def _has_dry_run(
    plans: Sequence[Mapping[str, Any]],
    results: Sequence[Mapping[str, Any]],
) -> bool:
    if any(bool(_field_value(plan, "dry_run")) for plan in plans):
        return True
    for result in results:
        if bool(_field_value(result, "dry_run")):
            return True
        decision = _nested_mapping(result, ("data", "policy_decision"))
        if bool(_field_value(decision, "dry_run")):
            return True
        metadata = _nested_mapping(result, ("data", "policy_metadata"))
        if bool(_field_value(metadata, "dry_run")):
            return True
    return False


def _nested_mapping(item: Mapping[str, Any], path: Sequence[str]) -> Mapping[str, Any]:
    current: Any = item
    for key in path:
        if not isinstance(current, Mapping):
            return {}
        current = current.get(key)
    return current if isinstance(current, Mapping) else {}


def _field_value(item: Mapping[str, Any], field: str) -> Any:
    return item.get(field) if isinstance(item, Mapping) else None


def _format_score(value: float | None) -> str:
    if value is None:
        return "None"
    return f"{value:.2f}"


def _round_score(value: float) -> float:
    return round(float(value), 4)


__all__ = [
    "DEFAULT_EVAL_THRESHOLDS",
    "EVAL_DIMENSIONS",
    "EvalCase",
    "EvalCaseResult",
    "EvalDeliveryExpectation",
    "EvalDimension",
    "EvalDimensionScore",
    "EvalExpectation",
    "EvalObservation",
    "EvalRunSummary",
    "EvalRunThresholdError",
    "EvalThresholdCheck",
    "EvalToolPolicyExpectation",
    "built_in_eval_cases",
    "run_eval_cases",
    "run_fixture_evals",
    "score_eval_case",
]
