from dataclasses import dataclass

from agent_studio.retrieval_workflow import build_query_plan, build_retrieval_pack


@dataclass
class Hit:
    id: str
    title: str
    category: str
    source_path: str
    score: float
    excerpt: str


def test_refund_query_plan_expands_policy_terms() -> None:
    plan = build_query_plan(
        message="I want my money back",
        intent="refund_or_cancellation",
        risk_level="high",
        selected_agent="support",
    )
    assert "refund policy" in plan.expanded_queries
    assert "supervisor review" in plan.expanded_queries
    assert plan.metadata_filters["approval_status"] == "approved"


def test_missing_knowledge_when_no_hits() -> None:
    plan = build_query_plan(
        message="Do you ship to Mars?",
        intent="shipping_question",
        risk_level="low",
        selected_agent="support",
    )
    pack = build_retrieval_pack(plan=plan, hits=[])
    assert pack.missing_knowledge is True
    assert pack.retrieval_confidence == 0.0


def test_relevant_policy_hit_creates_confident_pack() -> None:
    plan = build_query_plan(
        message="I want a refund",
        intent="refund_or_cancellation",
        risk_level="high",
        selected_agent="support",
    )
    hit = Hit(
        id="refund-policy:chunk:0",
        title="Refund Policy",
        category="policy",
        source_path="kb/refund.md",
        score=0.88,
        excerpt="Refunds are reviewed by a supervisor according to the refund policy.",
    )
    pack = build_retrieval_pack(plan=plan, hits=[hit])
    assert pack.selected_sources[0].title == "Refund Policy"
    assert pack.retrieval_confidence > 0.40
    assert pack.missing_knowledge is False


def test_duplicate_hits_keep_best_candidate() -> None:
    plan = build_query_plan(
        message="How long is shipping?",
        intent="shipping_question",
        risk_level="low",
        selected_agent="support",
    )
    hits = [
        Hit("ship:0", "Shipping FAQ", "faq", "kb/ship.md", 0.2, "Shipping takes time."),
        Hit("ship:0", "Shipping FAQ", "faq", "kb/ship.md", 0.9, "Shipping and delivery timeframe."),
    ]
    pack = build_retrieval_pack(plan=plan, hits=hits)
    assert len(pack.selected_sources) == 1
    assert pack.selected_sources[0].score > 0.8
