from agent_studio.retrieval_workflow import RetrievalPack, build_query_plan, build_retrieval_pack
from agent_studio.schemas import KnowledgeHit


def hit(
    id: str,
    title: str,
    category: str,
    score: float,
    excerpt: str,
    source_path: str = "kb/source.md",
) -> KnowledgeHit:
    return KnowledgeHit(
        id=id,
        title=title,
        category=category,
        source_path=source_path,
        score=score,
        excerpt=excerpt,
    )


def test_query_plan_normalizes_expands_and_sets_governed_filters() -> None:
    plan = build_query_plan(
        message="  I want my MONEY back  ",
        intent="refund_or_cancellation",
        risk_level="high",
        selected_agent="support",
        customer_driver="refund policy",
        candidate_limit=10,
        source_limit=3,
    )

    assert plan.raw_query == "  I want my MONEY back  "
    assert plan.normalized_query == "i want my money back"
    assert "refund policy" in plan.expanded_queries
    assert "supervisor review" in plan.expanded_queries
    assert plan.expanded_queries.count("refund policy") == 1
    assert plan.metadata_filters == {
        "approval_status": "approved",
        "intent": "refund_or_cancellation",
        "risk_level": "high",
        "selected_agent": "support",
    }
    assert plan.candidate_limit == 10
    assert plan.source_limit == 3


def test_reranking_orders_governed_hits_and_dedupes_by_hit_id() -> None:
    plan = build_query_plan(
        message="How long is shipping?",
        intent="shipping_question",
        risk_level="medium",
        selected_agent="support",
        source_limit=3,
    )
    hits = [
        hit(
            "shipping:chunk:0",
            "Shipping FAQ",
            "faq",
            0.2,
            "Shipping takes time.",
            "kb/shipping.md",
        ),
        hit(
            "shipping:chunk:0",
            "Shipping SOP",
            "sop",
            0.9,
            "Shipping timeframe, delivery estimate, and verification steps.",
            "kb/shipping.md",
        ),
        hit(
            "billing:chunk:0",
            "Billing Note",
            "templates",
            0.99,
            "Invoice wording for payment reminders.",
            "kb/billing.md",
        ),
    ]

    pack = build_retrieval_pack(plan=plan, hits=hits)

    assert isinstance(pack, RetrievalPack)
    assert [source.id for source in pack.selected_sources] == [
        "shipping:chunk:0",
        "billing:chunk:0",
    ]
    assert pack.selected_sources[0].title == "Shipping SOP"
    assert pack.selected_sources[0].score > 0.8
    assert "category boost: sop" in pack.selected_sources[0].reasons


def test_confidence_is_high_for_relevant_diverse_source_coverage() -> None:
    plan = build_query_plan(
        message="Can I get a refund after cancellation?",
        intent="refund_or_cancellation",
        risk_level="high",
        selected_agent="support",
        source_limit=4,
    )

    pack = build_retrieval_pack(
        plan=plan,
        hits=[
            hit(
                "refund-policy:chunk:0",
                "Refund Policy",
                "policy",
                0.88,
                "Refund requests follow the refund policy and supervisor review process.",
            ),
            hit(
                "cancellation-sop:chunk:0",
                "Cancellation SOP",
                "sop",
                0.76,
                "Cancellation requests require verification and support procedure steps.",
            ),
            hit(
                "refund-faq:chunk:0",
                "Refund FAQ",
                "faq",
                0.7,
                "FAQ for refund window and return eligibility.",
            ),
        ],
    )

    assert pack.retrieval_confidence >= 0.6
    assert pack.retrieval_confidence <= 1.0
    assert pack.missing_knowledge is False
    assert "selected 3 source(s) from 3 candidate(s)" in pack.reasons


def test_missing_knowledge_when_no_hits_are_available() -> None:
    plan = build_query_plan(
        message="Do you ship to Mars?",
        intent="shipping_question",
        risk_level="low",
        selected_agent="support",
    )

    pack = build_retrieval_pack(plan=plan, hits=[])

    assert pack.selected_sources == []
    assert pack.retrieval_confidence == 0.0
    assert pack.missing_knowledge is True
    assert "no approved sources retrieved" in pack.reasons


def test_missing_knowledge_when_only_weak_generic_source_is_available() -> None:
    plan = build_query_plan(
        message="What warranty applies to a custom enterprise contract?",
        intent="general_support",
        risk_level="high",
        selected_agent="support",
    )

    pack = build_retrieval_pack(
        plan=plan,
        hits=[
            hit(
                "template:chunk:0",
                "General Reply Template",
                "templates",
                0.1,
                "Friendly opening line for a standard answer.",
            ),
        ],
    )

    assert pack.missing_knowledge is True
    assert pack.retrieval_confidence < 0.4
    assert "only generic source retrieved" in pack.reasons


def test_reranker_reorders_hits(monkeypatch) -> None:
    from unittest.mock import MagicMock
    from agent_studio.retrieval import _rerank_hits
    from agent_studio.config import Settings

    mock_rerank = MagicMock()
    mock_response = MagicMock()
    mock_response.results = [
        MagicMock(index=1, relevance_score=0.95),
        MagicMock(index=0, relevance_score=0.45)
    ]
    mock_rerank.return_value = mock_response

    monkeypatch.setattr("litellm.rerank", mock_rerank)

    settings = Settings(
        rerank_enabled=True,
        rerank_model="cohere/rerank-english-v3.0"
    )

    hits = [
        hit("id:0", "Title 0", "category", 0.9, "First excerpt content"),
        hit("id:1", "Title 1", "category", 0.5, "Second excerpt content")
    ]

    reranked = _rerank_hits("query text", hits, limit=2, settings=settings)

    assert len(reranked) == 2
    assert reranked[0].id == "id:1"
    assert reranked[0].score == 0.95
    assert reranked[1].id == "id:0"
    assert reranked[1].score == 0.45


def test_openrouter_reranker_direct(monkeypatch) -> None:
    from unittest.mock import MagicMock
    from agent_studio.retrieval import _rerank_hits
    from agent_studio.config import Settings

    mock_post = MagicMock()
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "results": [
            {"index": 1, "relevance_score": 0.98},
            {"index": 0, "relevance_score": 0.35}
        ]
    }
    mock_post.return_value = mock_response

    monkeypatch.setattr("httpx.Client.post", mock_post)

    settings = Settings(
        rerank_enabled=True,
        rerank_model="openrouter/cohere/rerank-v3.5",
        rerank_api_key="sk-or-testkey"
    )

    hits = [
        hit("id:0", "Title 0", "category", 0.9, "First excerpt content"),
        hit("id:1", "Title 1", "category", 0.5, "Second excerpt content")
    ]

    reranked = _rerank_hits("query text", hits, limit=2, settings=settings)

    assert len(reranked) == 2
    assert reranked[0].id == "id:1"
    assert reranked[0].score == 0.98
    assert reranked[1].id == "id:0"
    assert reranked[1].score == 0.35

    assert mock_post.call_count == 1
    call_args = mock_post.call_args
    assert call_args[0][0] == "https://openrouter.ai/api/v1/rerank"
    assert "Authorization" in call_args[1]["headers"]
    assert "Bearer sk-or-testkey" == call_args[1]["headers"]["Authorization"]
    assert call_args[1]["json"]["model"] == "cohere/rerank-v3.5"
