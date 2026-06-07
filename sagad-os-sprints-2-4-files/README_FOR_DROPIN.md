# Sagad OS Sprint 2-4 Drop-In Pack

This pack assumes Sprint 1 is already functionally complete:

```text
Chatwoot inbound -> classified -> routed -> agent -> confidence -> guardrails -> HITL -> approved send/dry-run -> audit
```

Sprint 2-4 should now mature the system from a working demo into a credible AI-native BPO operations foundation.

## Sprint Focus

| Sprint | Theme | Outcome |
|---|---|---|
| Sprint 2 | Optimized retrieval | Agents retrieve the right approved source, detect missing knowledge, and produce grounded source packs. |
| Sprint 3 | Skills, tools, MCP boundary | Agents can use internal skills and server-side tools through policy gates; MCP remains behind Agent Studio, not exposed raw. |
| Sprint 4 | Evals, observability, hardening | The system can measure retrieval, decision quality, tool safety, and operational reliability. |

## Files In This Pack

```text
docs/blueprints/sprints-2-4-master-roadmap.md
docs/blueprints/sprint-2-optimized-retrieval.md
docs/blueprints/sprint-3-skills-tools-mcp.md
docs/blueprints/sprint-4-evals-observability-hardening.md
docs/blueprints/sprints-2-4-reference-architecture.md
docs/blueprints/sprints-2-4-implementation-file-map.md
docs/blueprints/retrieval-eval-playbook.md

agent-studio/agent_studio/retrieval_workflow.py
agent-studio/agent_studio/confidence.py
agent-studio/agent_studio/guardrails.py
agent-studio/agent_studio/tool_policy.py
agent-studio/agent_studio/skill_registry.py
agent-studio/agent_studio/mcp_gateway.py
agent-studio/agent_studio/evals.py
agent-studio/agent_studio/observability.py

agent-studio/tests/test_retrieval_workflow.py
agent-studio/tests/test_tool_policy.py
agent-studio/tests/test_skill_registry.py
agent-studio/tests/test_evals.py

agent-studio/migrations/0002_ai_ops_quality_layer.sql
```

## Apply Order

1. Add the blueprint docs first.
2. Add the new Python modules under `agent-studio/agent_studio/`.
3. Add the tests under `agent-studio/tests/`.
4. Add the migration only after reviewing table names against the current foundation migration.
5. Wire the modules into `graph.py` in this order:
   - `retrieval_workflow.py`
   - `confidence.py`
   - `guardrails.py`
   - `tool_policy.py`
   - `observability.py`
6. Update `schemas.py`, `state.py`, and `v1/docs/backend-contracts.md` after the graph output shape is stable.

## Integration Principle

Do not let Sprint 3 create uncontrolled agent autonomy.

The platform rule remains:

```text
AI proposes.
Agent Studio verifies.
Humans approve when risk exists.
Every action is logged.
```
