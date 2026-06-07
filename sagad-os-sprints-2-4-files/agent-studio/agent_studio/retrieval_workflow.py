"""Governed retrieval workflow helpers for Sagad OS Sprint 2.

This module wraps the existing low-level retriever. It does not replace
`agent_studio.retrieval`. Keep provider-specific vector/pgvector behavior there.

Purpose:
- build a better retrieval query;
- normalize and rerank candidate hits;
- detect missing knowledge;
- produce retrieval confidence that can feed final confidence scoring.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, Protocol


class KnowledgeHitLike(Protocol):
    id: str
    title: str
    category: str
    source_path: str
    score: float
    excerpt: str


@dataclass(frozen=True)
class RetrievalQueryPlan:
    raw_query: str
    normalized_query: str
    intent: str
    risk_level: str
    selected_agent: str
    expanded_queries: list[str] = field(default_factory=list)
    metadata_filters: dict[str, object] = field(default_factory=dict)
    candidate_limit: int = 8
    source_limit: int = 4


@dataclass(frozen=True)
class RetrievalCandidate:
    id: str
    title: str
    category: str
    source_path: str
    score: float
    excerpt: str
    rerank_score: float
    reasons: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class RetrievalPack:
    plan: RetrievalQueryPlan
    selected_sources: list[RetrievalCandidate]
    retrieval_confidence: float
    missing_knowledge: bool
    reasons: list[str] = field(default_factory=list)


INTENT_EXPANSIONS: dict[str, list[str]] = {
    "refund_or_cancellation": [
        "refund policy",
        "return eligibility",
        "cancellation request",
        "compensation policy",
        "refund window",
    ],
    "shipping_question": [
        "shipping timeframe",
        "delivery estimate",
        "fulfillment policy",
        "shipping FAQ",
    ],
    "order_status": [
        "order status",
        "tracking",
        "delivery update",
        "account verification",
    ],
    "pricing_lead": [
        "pricing",
        "quote",
        "cost",
        "purchase readiness",
    ],
    "sizing_or_product_question": [
        "size guide",
        "product availability",
        "variant availability",
        "fit question",
    ],
    "general_support": [
        "support policy",
        "FAQ",
        "escalation rules",
    ],
}

RISK_EXPANSIONS: dict[str, list[str]] = {
    "low": ["FAQ", "standard answer"],
    "medium": ["SOP", "verification", "support procedure"],
    "high": ["policy", "escalation", "supervisor review", "compliance"],
}

CATEGORY_BOOSTS: dict[str, float] = {
    "policy": 0.18,
    "policies": 0.18,
    "sop": 0.15,
    "sops": 0.15,
    "faq": 0.12,
    "faqs": 0.12,
    "compliance": 0.20,
    "qa": 0.08,
    "templates": 0.04,
}


def normalize_query_text(value: str) -> str:
    """Normalize user text for deterministic retrieval planning."""
    return " ".join(value.strip().lower().split())


def build_query_plan(
    *,
    message: str,
    intent: str,
    risk_level: str,
    selected_agent: str,
    customer_driver: str | None = None,
    candidate_limit: int = 8,
    source_limit: int = 4,
) -> RetrievalQueryPlan:
    """Create a governed retrieval query plan from classified state."""
    normalized = normalize_query_text(message)
    expanded: list[str] = []
    expanded.extend(INTENT_EXPANSIONS.get(intent, []))
    expanded.extend(RISK_EXPANSIONS.get(risk_level, []))
    if customer_driver:
        expanded.append(customer_driver)
    # Preserve order while removing duplicates.
    deduped_expansions = list(dict.fromkeys(expanded))
    metadata_filters: dict[str, object] = {
        "approval_status": "approved",
        "intent": intent,
        "risk_level": risk_level,
        "selected_agent": selected_agent,
    }
    return RetrievalQueryPlan(
        raw_query=message,
        normalized_query=normalized,
        intent=intent,
        risk_level=risk_level,
        selected_agent=selected_agent,
        expanded_queries=deduped_expansions,
        metadata_filters=metadata_filters,
        candidate_limit=candidate_limit,
        source_limit=source_limit,
    )


def _bounded_score(score: float) -> float:
    """Convert heterogeneous retriever scores to a 0-1-ish range.

    pgvector similarity is typically already <= 1. The in-memory preview retriever
    can return token-overlap scores above 1, so compress those safely.
    """
    if score <= 0:
        return 0.0
    if score <= 1:
        return float(score)
    return min(1.0, score / (score + 4.0))


def _text_overlap(query: str, text: str) -> float:
    query_terms = set(normalize_query_text(query).split())
    text_terms = set(normalize_query_text(text).split())
    if not query_terms:
        return 0.0
    return len(query_terms & text_terms) / len(query_terms)


def _category_boost(category: str) -> float:
    return CATEGORY_BOOSTS.get(category.strip().lower(), 0.0)


def rerank_hit(hit: KnowledgeHitLike, plan: RetrievalQueryPlan) -> RetrievalCandidate:
    """Rerank a low-level retriever hit with governance-aware signals."""
    base = _bounded_score(float(hit.score))
    title_text = f"{hit.title} {hit.category} {hit.excerpt}"
    overlap = _text_overlap(plan.normalized_query, title_text)
    expansion_overlap = max(
        [_text_overlap(expanded, title_text) for expanded in plan.expanded_queries] or [0.0],
    )
    category_boost = _category_boost(hit.category)
    risk_boost = 0.05 if plan.risk_level in title_text.lower() else 0.0
    intent_boost = 0.08 if plan.intent.replace("_", " ") in title_text.lower() else 0.0
    rerank_score = min(
        1.0,
        (base * 0.55)
        + (overlap * 0.15)
        + (expansion_overlap * 0.12)
        + category_boost
        + risk_boost
        + intent_boost,
    )
    reasons: list[str] = []
    if base >= 0.55:
        reasons.append("strong retriever score")
    if overlap > 0:
        reasons.append("query term overlap")
    if expansion_overlap > 0:
        reasons.append("expanded query overlap")
    if category_boost > 0:
        reasons.append(f"category boost: {hit.category}")
    if risk_boost:
        reasons.append("risk-level match")
    if intent_boost:
        reasons.append("intent match")
    return RetrievalCandidate(
        id=str(hit.id),
        title=str(hit.title),
        category=str(hit.category),
        source_path=str(hit.source_path),
        score=base,
        excerpt=str(hit.excerpt),
        rerank_score=rerank_score,
        reasons=reasons,
    )


def dedupe_candidates(candidates: Iterable[RetrievalCandidate]) -> list[RetrievalCandidate]:
    """Keep the best candidate per source/chunk id."""
    best: dict[str, RetrievalCandidate] = {}
    for candidate in candidates:
        existing = best.get(candidate.id)
        if existing is None or candidate.rerank_score > existing.rerank_score:
            best[candidate.id] = candidate
    return sorted(best.values(), key=lambda item: item.rerank_score, reverse=True)


def score_retrieval_confidence(selected_sources: list[RetrievalCandidate], *, source_limit: int = 4) -> float:
    if not selected_sources:
        return 0.0
    top_score = selected_sources[0].rerank_score
    coverage_score = min(1.0, len(selected_sources) / max(source_limit, 1))
    second_source_score = selected_sources[1].rerank_score if len(selected_sources) > 1 else 0.0
    diversity_score = min(1.0, len({source.category for source in selected_sources}) / 3.0)
    confidence = (
        top_score * 0.50
        + coverage_score * 0.20
        + second_source_score * 0.15
        + diversity_score * 0.10
        + 0.05
    )
    return round(max(0.0, min(1.0, confidence)), 4)


def detect_missing_knowledge(
    selected_sources: list[RetrievalCandidate],
    *,
    minimum_top_score: float = 0.35,
    minimum_confidence: float = 0.40,
    retrieval_confidence: float | None = None,
) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    if not selected_sources:
        return True, ["no approved sources retrieved"]
    top_score = selected_sources[0].rerank_score
    if top_score < minimum_top_score:
        reasons.append("top source score below threshold")
    if retrieval_confidence is not None and retrieval_confidence < minimum_confidence:
        reasons.append("retrieval confidence below threshold")
    generic_categories = {"general", "templates"}
    if len(selected_sources) == 1 and selected_sources[0].category.lower() in generic_categories:
        reasons.append("only generic source retrieved")
    return bool(reasons), reasons


def build_retrieval_pack(
    *,
    plan: RetrievalQueryPlan,
    hits: Iterable[KnowledgeHitLike],
    minimum_top_score: float = 0.35,
    minimum_confidence: float = 0.40,
) -> RetrievalPack:
    reranked = dedupe_candidates(rerank_hit(hit, plan) for hit in hits)
    selected = reranked[: plan.source_limit]
    confidence = score_retrieval_confidence(selected, source_limit=plan.source_limit)
    missing, missing_reasons = detect_missing_knowledge(
        selected,
        minimum_top_score=minimum_top_score,
        minimum_confidence=minimum_confidence,
        retrieval_confidence=confidence,
    )
    reasons: list[str] = []
    if selected:
        reasons.append(f"selected {len(selected)} source(s) from {len(reranked)} candidate(s)")
    reasons.extend(missing_reasons)
    return RetrievalPack(
        plan=plan,
        selected_sources=selected,
        retrieval_confidence=confidence,
        missing_knowledge=missing,
        reasons=reasons,
    )
