# Sprint 2: Optimized Retrieval

Sprint 2 upgrades Sagad Knowledge from a working RAG layer into a governed retrieval workflow.

## Problem

A basic vector search is not enough for BPO operations.

Bad retrieval creates:

- hallucinated answers;
- low-confidence drafts;
- false auto-send risk;
- supervisor distrust;
- hidden knowledge gaps;
- weak client reporting.

## Sprint 2 Thesis

Retrieval is not a database query. It is a decision workflow.

```text
customer message
-> normalize
-> classify intent/risk/driver
-> choose agent
-> build retrieval query
-> apply governance filters
-> retrieve approved sources
-> rerank
-> build source pack
-> score retrieval confidence
-> detect missing knowledge
-> feed confidence + guardrails
```

## Required Workflow

### 1. Query Planning

Input:

```text
message
intent
risk_level
selected_agent
customer_driver
```

Output:

```text
normalized_query
expanded_queries
metadata_filters
candidate_limit
rerank_limit
```

The planner should expand query meaning without broadening into unsafe guessing.

Example:

```text
Customer: "I want my money back"
Intent: refund_or_cancellation
Expanded queries:
- refund policy
- return eligibility
- cancellation request
- compensation policy
```

### 2. Governance Filtering

Hard filters:

```text
organization_id == current workspace
approval_status == approved
archived == false
```

Soft filters / boosts:

```text
allowed_agents includes selected_agent
metadata.intents includes detected intent
metadata.risk_levels includes risk_level
category in policy/sop/faq/compliance/qa
latest approved version
```

### 3. Candidate Retrieval

Sprint 2 can wrap the current retriever rather than replacing it.

Current foundation:

```text
retriever.search(query, intent, risk_level, limit, context)
```

Sprint 2 wrapper:

```text
build_query_plan(...)
-> retriever.search(plan.normalized_query, ...)
-> rerank candidates locally
-> build RetrievalPack
```

### 4. Reranking

Initial reranking can be deterministic:

| Signal | Purpose |
|---|---|
| vector score | semantic similarity |
| title/category match | boosts policy/FAQ/SOP relevance |
| intent match | boosts task-fit |
| risk match | prevents low-risk content from supporting high-risk actions |
| agent match | prevents Sales agent from using Support-only policy blindly |
| exact keyword overlap | catches domain terms vector search may flatten |

A model-based reranker can come later. Do not introduce it until deterministic scoring is measured.

### 5. Source Pack

A source pack must include:

```text
source id
title
category
source path
score
excerpt
why selected
confidence contribution
```

The agent should draft only from the source pack.

### 6. Missing Knowledge Detection

Set `missing_knowledge=true` when:

```text
no approved hit exists
best score is below threshold
only generic source appears for specific policy question
source category conflicts with intent
retrieved source cannot answer the requested action
```

### 7. Retrieval Confidence

Initial retrieval confidence:

```text
retrieval_confidence =
  top_source_score * 0.50
+ source_coverage_score * 0.20
+ intent_match_score * 0.15
+ source_diversity_score * 0.10
+ freshness_score * 0.05
```

Do not confuse retrieval confidence with final answer confidence. Retrieval confidence is only one component of the full confidence rubric.

## New Backend Module

```text
agent-studio/agent_studio/retrieval_workflow.py
```

This file should own:

```text
RetrievalQueryPlan
RetrievalCandidate
RetrievalPack
build_query_plan
build_retrieval_pack
score_retrieval_confidence
detect_missing_knowledge
```

## State Fields To Add

```text
retrieval_query: str
retrieval_expanded_queries: list[str]
retrieval_filters: dict[str, object]
retrieval_confidence: float
missing_knowledge: bool
retrieval_reasons: list[str]
```

## Tests

```text
agent-studio/tests/test_retrieval_workflow.py
```

Required tests:

- refund query expands into refund/cancellation terms;
- low-score/no-source result triggers missing knowledge;
- approved high-score result does not trigger missing knowledge;
- duplicate hits are collapsed;
- retrieval confidence stays between 0 and 1.

## Sprint 2 Demo Cases

| Message | Expected retrieval behavior |
|---|---|
| `I want a refund.` | refund policy first; high risk; HITL |
| `How long does shipping take?` | shipping FAQ first; low or medium risk |
| `Can I exchange for another size?` | returns/exchange policy first |
| `Can you waive my fee?` | compensation/refund policy or missing knowledge |
| `Do you ship to Mars?` | missing knowledge |

## Exit Gate

Sprint 2 is done when retrieval can be inspected and evaluated independently from draft quality.

If the answer is wrong, the operator should know whether the failure came from:

```text
classification
query planning
retrieval
missing knowledge
drafting
guardrails
tool policy
```
