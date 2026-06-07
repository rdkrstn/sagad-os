# Sprints 2-4 Master Roadmap

Sprint 1 proves the live supervised loop. Sprints 2-4 make that loop reliable, extensible, and measurable.

## North Star

By the end of Sprint 4, Sagad OS should be able to run a BPO-grade AI operations demo where a customer message is not only answered, but operationally explained:

```text
What happened?
Why did the system route it there?
What knowledge did it use?
What tools were available?
Which tools were blocked?
How confident was the answer?
Which guardrails fired?
Why did a human need to approve it?
What was sent?
What was logged?
How does the system improve from this case?
```

## Sprint 2: Optimized Retrieval

### Goal

Move from basic RAG to governed retrieval quality.

The agent must retrieve the right approved knowledge, attach useful evidence, flag missing knowledge, and produce retrieval confidence that feeds the decision engine.

### Deliverables

- Retrieval query planner.
- Intent/risk/agent-aware metadata filters.
- Hybrid-style scoring wrapper over current pgvector/in-memory retriever.
- Source pack builder.
- Missing-knowledge detector.
- Retrieval confidence scoring.
- Retrieval eval dataset and scorecard.
- Knowledge gap logging.

### Exit Criteria

- Approved documents only.
- No unapproved source can reach the agent context.
- Refund questions retrieve refund policy before generic support.
- Shipping questions retrieve shipping FAQ before generic support.
- Unknown or unsupported topics trigger `missing_knowledge=true`.
- Approval card shows source title, excerpt, score, and why it was used.
- Retrieval test cases run locally without live provider credentials.

## Sprint 3: Skills, Tools, MCP Boundary

### Goal

Make agentic capability real without exposing uncontrolled tools.

The system should support internal skills, server-side tools, and future MCP servers through one policy boundary owned by Agent Studio.

### Deliverables

- Skill registry for internal agent capabilities.
- Tool capability manifests.
- Tool policy evaluator.
- Read/write/dry-run distinction.
- Risk-aware tool gates.
- Tool plan and result correlation.
- MCP gateway design that exposes only approved tool descriptors.
- Tool audit events.

### Exit Criteria

- Agents can discover internal skills and approved tools.
- Read tools can run when workspace, role, risk, and agent policy allow it.
- Write tools require explicit approval.
- High-risk conversations cannot execute live write tools automatically.
- Every tool plan produces a policy decision before execution.
- Every tool result links back to the originating plan.
- MCP is not raw direct access; it is a facade behind Agent Studio policy.

## Sprint 4: Evals, Observability, Hardening

### Goal

Make the system measurable and debuggable.

The operator should not need Docker logs to understand failures, retrieval gaps, bad drafts, or blocked tool calls.

### Deliverables

- Evaluation case format.
- Retrieval eval suite.
- Routing eval suite.
- Guardrail eval suite.
- Tool policy eval suite.
- Confidence calibration scorecard.
- Audit event taxonomy.
- Trace attribute schema.
- Redaction rules for telemetry payloads.
- AI Ops dashboard requirements.

### Exit Criteria

- A maintainer can run evals before changing prompts, retrieval, guardrails, or tool policy.
- Retrieval success, missing-knowledge detection, tool block rate, approval rate, and send failure rate are visible.
- Every failed provider action has a visible failure category.
- Every graph node has a clear event/span naming convention.
- Sensitive payload fields are redacted before diagnostics and traces.

## Do Not Add Yet

These remain post-Sprint 4 unless a real pilot forces them earlier:

```text
Temporal
Kubernetes-first deployment
OPA/Rego production policy engine
Full MCP marketplace
Multi-provider model router complexity beyond LiteLLM readiness
External KB sync sprawl
Native Zendesk/Intercom adapters
Enterprise BI
Full QA scoring engine
```

## Sprint 2-4 Success Metric

The demo is successful when the approval card can answer:

```text
Why this draft?
Why this source?
Why this agent?
Why this confidence?
Why HITL?
Why this tool action or block?
What happens next?
```
