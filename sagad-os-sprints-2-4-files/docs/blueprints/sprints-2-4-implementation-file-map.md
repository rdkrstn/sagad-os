# Sprints 2-4 Implementation File Map

This is the practical file-by-file guide.

## Sprint 2 Files

### Add

```text
agent-studio/agent_studio/retrieval_workflow.py
agent-studio/tests/test_retrieval_workflow.py
docs/blueprints/sprint-2-optimized-retrieval.md
docs/blueprints/retrieval-eval-playbook.md
```

### Modify

```text
agent-studio/agent_studio/graph.py
agent-studio/agent_studio/state.py
agent-studio/agent_studio/schemas.py
agent-studio/agent_studio/retrieval.py
v1/docs/backend-contracts.md
```

### State Fields

```text
selected_agent
customer_driver
urgency
retrieval_query
retrieval_expanded_queries
retrieval_filters
retrieval_confidence
retrieval_reasons
missing_knowledge
```

## Sprint 3 Files

### Add

```text
agent-studio/agent_studio/skill_registry.py
agent-studio/agent_studio/tool_policy.py
agent-studio/agent_studio/mcp_gateway.py
agent-studio/tests/test_skill_registry.py
agent-studio/tests/test_tool_policy.py
docs/blueprints/sprint-3-skills-tools-mcp.md
```

### Modify

```text
agent-studio/agent_studio/graph.py
agent-studio/agent_studio/state.py
agent-studio/agent_studio/schemas.py
agent-studio/agent_studio/main.py
agent-studio/agent_studio/store.py
v1/docs/backend-contracts.md
v1/src/lib/api/index.ts
```

### State Fields

```text
available_skills
planned_skills
tool_policy_decisions
tool_plans
tool_results
requires_tool_approval
blocked_tools
```

## Sprint 4 Files

### Add

```text
agent-studio/agent_studio/evals.py
agent-studio/agent_studio/observability.py
agent-studio/tests/test_evals.py
agent-studio/migrations/0002_ai_ops_quality_layer.sql
docs/blueprints/sprint-4-evals-observability-hardening.md
```

### Modify

```text
agent-studio/agent_studio/main.py
agent-studio/agent_studio/store.py
agent-studio/agent_studio/schemas.py
agent-studio/tests/test_app.py
v1/src/lib/api/index.ts
v1 dashboard/reporting components
```

### State Fields

```text
eval_tags
trace_attributes
diagnostic_payload
decision_reason
guardrail_findings
confidence_breakdown
final_confidence_score
```

## Suggested PR Sequence

### PR 1: Retrieval Workflow Foundation

```text
add retrieval_workflow.py
add test_retrieval_workflow.py
wire build_query_plan + build_retrieval_pack into graph.py
add retrieval fields to state.py and schemas.py
```

### PR 2: Retrieval Visibility In Console

```text
update API DTOs
show retrieval query
show selected sources
show missing knowledge
show retrieval confidence
```

### PR 3: Skills And Tool Policy Foundation

```text
add skill_registry.py
add tool_policy.py
add test_skill_registry.py
add test_tool_policy.py
wire plan_tools and policy decisions into graph.py
```

### PR 4: MCP Gateway Placeholder

```text
add mcp_gateway.py
expose descriptor generation only
no live raw MCP execution yet
```

### PR 5: Evals Foundation

```text
add evals.py
add eval fixtures
add scorecard logic
run evals in CI later
```

### PR 6: Observability Hardening

```text
add observability.py
standardize event names
redact diagnostic payloads
attach trace attributes
```

## Do Not Combine

Do not ship retrieval overhaul, tool policy, MCP gateway, and evals in one PR. It will become impossible to know which layer broke the loop.
