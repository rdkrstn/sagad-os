# Sprint 4: Evals, Observability, And Hardening

Sprint 4 turns Sagad OS from a working controlled demo into an inspectable operating system.

## Problem

If operators cannot measure the system, they cannot trust it.

AI failures are usually not isolated model failures. They are chain failures:

```text
bad classification
bad routing
bad retrieval
missing knowledge
unsafe tool plan
weak draft
bad confidence calibration
guardrail bypass
provider send failure
```

Sprint 4 makes those failures visible and testable.

## Sprint 4 Thesis

Every graph decision should produce:

```text
state change
audit event
optional trace span
eval-compatible output
operator-visible diagnostic
```

## Evaluation Layers

| Layer | Question |
|---|---|
| Classification eval | Did we identify the correct intent, driver, urgency, and risk? |
| Routing eval | Did the right agent receive the case? |
| Retrieval eval | Did approved relevant knowledge appear in top results? |
| Missing-knowledge eval | Did unsupported questions get flagged? |
| Draft eval | Is the response grounded and policy-safe? |
| Guardrail eval | Did the right block/HITL/escalation fire? |
| Tool policy eval | Were risky tools blocked or approval-gated? |
| Delivery eval | Did send/dry-run/failure state resolve correctly? |

## Eval Case Format

```json
{
  "id": "refund_basic_001",
  "message": "I want a refund.",
  "expected_intent": "refund_or_cancellation",
  "expected_agent": "support",
  "expected_risk_level": "high",
  "expected_sources_any": ["refund-policy"],
  "expected_missing_knowledge": false,
  "expected_decision": "hitl",
  "blocked_tools": ["chatwoot.send_approved_reply"]
}
```

## Scorecard

Sprint 4 target thresholds for demo readiness:

| Metric | Target |
|---|---:|
| Intent match | >= 85% |
| Agent route match | >= 90% |
| Top-3 retrieval hit | >= 85% |
| Unapproved source leakage | 0% |
| Missing-knowledge detection | >= 80% |
| High-risk auto-send incidents | 0 |
| Tool write without approval | 0 |
| Provider failure visible in diagnostics | 100% |

These are demo-readiness thresholds, not enterprise guarantees.

## Observability Events

Required event taxonomy:

```text
conversation.received
conversation.ignored
message.normalized
message.classified
agent.routed
retrieval.planned
retrieval.completed
retrieval.missing_knowledge
tool.planned
tool.policy_allowed
tool.policy_blocked
tool.executed
tool.failed
draft.generated
confidence.scored
guardrails.applied
approval.created
approval.updated
delivery.dry_run
delivery.sent
delivery.failed
```

## Trace Naming

Use stable span names:

```text
sagad.graph.normalize
sagad.graph.classify
sagad.graph.route_agent
sagad.graph.retrieve
sagad.graph.plan_tools
sagad.graph.draft
sagad.graph.score_confidence
sagad.graph.apply_guardrails
sagad.graph.decide_delivery
sagad.tool.policy
sagad.tool.execute
sagad.delivery.chatwoot
```

## Redaction Rules

Never expose raw:

```text
api keys
tokens
webhook secrets
full customer emails
full phone numbers
payment details
full provider response bodies
PII-heavy transcripts
```

Diagnostics should use:

```text
masked email
masked phone
clipped response body
error code
provider status
tool name
risk level
conversation id
workspace id
```

## Dashboard Requirements

Minimum AI Ops dashboard:

```text
messages received
AI drafts generated
approval required rate
auto-send candidate rate
actual auto-send rate
retrieval missing-knowledge rate
average retrieval confidence
average final confidence
high-risk case count
tool calls planned
tool calls blocked
tool dry-runs
tool failures
send failures
escalation rate
```

## Hardening Checklist

Sprint 4 does not require enterprise hardening, but it must close preview-grade holes:

```text
idempotency checks for webhooks
provider timeout categories
retry-safe dry-run behavior
clear error taxonomy
clipped diagnostic payloads
stable eval fixtures
migration safety notes
test coverage for high-risk paths
operator-visible failure states
```

## Exit Gate

Sprint 4 is done when a maintainer can run:

```text
pytest agent-studio/tests/test_retrieval_workflow.py
pytest agent-studio/tests/test_tool_policy.py
pytest agent-studio/tests/test_evals.py
```

And answer:

```text
What got worse after this change?
Which cases regressed?
Which source failed retrieval?
Which guardrail failed?
Which tool was blocked and why?
```
