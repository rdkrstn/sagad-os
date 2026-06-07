# Retrieval Eval Playbook

Use this playbook to measure Sprint 2 retrieval quality before tuning prompts or tool behavior.

## Eval Case Shape

```json
{
  "id": "shipping_basic_001",
  "message": "How long does shipping take?",
  "intent": "shipping_question",
  "risk_level": "low",
  "selected_agent": "support",
  "expected_source_keywords": ["shipping", "delivery"],
  "expected_missing_knowledge": false,
  "notes": "Should retrieve shipping FAQ or fulfillment SOP."
}
```

## Minimum Seed Set

| ID | Message | Expected |
|---|---|---|
| `refund_001` | `I want a refund.` | refund/returns policy, HITL |
| `refund_002` | `Can I get my money back if I already used it?` | refund policy or missing knowledge |
| `shipping_001` | `How long does shipping take?` | shipping FAQ |
| `shipping_002` | `Do you ship internationally?` | shipping/international policy or missing knowledge |
| `order_001` | `Where is my order?` | order-status SOP + account verification risk |
| `sizing_001` | `Do you have this in medium?` | sizing/product availability path |
| `angry_001` | `This is unacceptable.` | escalation/angry customer handling |
| `legal_001` | `I want to sue you.` | escalation/legal guardrail |
| `unknown_001` | `Can you repair my motorcycle?` | missing knowledge |
| `policy_conflict_001` | `Your website says one thing but your agent said another.` | policy conflict + HITL |

## Metrics

### Top-K Source Hit

```text
Did an expected source appear in top 1, top 3, or top 5?
```

### Missing-Knowledge Accuracy

```text
Did unsupported questions get marked as missing knowledge?
```

### Source Leakage

```text
Did an unapproved, archived, or wrong-workspace source appear?
```

Target: zero leakage.

### Rerank Quality

```text
Did the most useful source appear before generic content?
```

### Confidence Calibration

```text
Do weak retrieval cases produce lower retrieval_confidence?
```

## Manual Review Rubric

| Score | Meaning |
|---:|---|
| 1.0 | Exact approved source answers the question. |
| 0.8 | Relevant approved source mostly answers the question. |
| 0.6 | Related source but incomplete answer. |
| 0.4 | Generic source; requires human judgment. |
| 0.2 | Weak source; should probably be missing knowledge. |
| 0.0 | No relevant source or unsafe source. |

## Review Cadence

Run retrieval evals when changing:

```text
chunking
embedding model
metadata filters
query expansion
classification labels
knowledge packs
rerank scoring
missing-knowledge thresholds
```
