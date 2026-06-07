# Sprint 3: Skills, Tools, And MCP Boundary

Sprint 3 makes the system agentic without making it reckless.

## Problem

An AI-native BPO platform cannot stop at drafting replies. It needs controlled access to operational capabilities:

```text
look up customer
search knowledge
summarize conversation
create internal note
prepare task
request supervisor approval
send approved reply
```

But raw tools create risk:

- unauthorized writes;
- privilege escalation;
- prompt injection;
- data leakage;
- silent CRM corruption;
- client trust failures.

## Sprint 3 Thesis

Do not expose tools directly to the model.

Use this chain:

```text
Agent intent
-> skill registry
-> tool plan
-> policy evaluation
-> dry-run or approval gate
-> execution
-> tool result
-> audit event
```

## Definitions

| Layer | Meaning | Example |
|---|---|---|
| Skill | Internal capability used by Sagad agents | classify, retrieve, draft, score, summarize |
| Tool | Server-side executable capability | search KB, get CRM contact, create note |
| Adapter | Provider-specific implementation | Chatwoot, Twenty, generic webhook |
| MCP | Protocol facade for externalized tools/resources/prompts | future MCP server behind Agent Studio |

## Skill Registry

Create:

```text
agent-studio/agent_studio/skill_registry.py
```

A skill is not necessarily an external action. It is a capability the graph can call or describe.

Required default skills:

```text
classify_message
route_agent
retrieve_knowledge
summarize_thread
plan_tools
draft_reply
score_confidence
apply_guardrails
create_approval_item
```

Each skill should declare:

```text
name
description
category
allowed_agents
requires_model
requires_tools
risk_level
```

## Tool Policy

Create:

```text
agent-studio/agent_studio/tool_policy.py
```

Every tool requires a manifest:

```text
tool_name
provider
skill_name
mode: read | write | dry_run
risk_level
allowed_agents
requires_approval
enabled
dry_run_default
input_schema
```

Every tool call requires a policy decision before execution.

Policy decision:

```text
allowed: bool
requires_approval: bool
dry_run: bool
blocked_reason: str | None
policy_reasons: list[str]
```

## Default Tool Manifests

| Tool | Mode | Risk | Approval |
|---|---|---:|---:|
| `knowledge.search` | read | low | no |
| `crm.lookup_contact` | read | medium | no for supervisor-reviewed contexts |
| `crm.create_note` | write | medium | yes |
| `crm.create_task` | write | medium | yes |
| `crm.update_lead_stage` | write | high | yes |
| `chatwoot.send_approved_reply` | write | medium/high | yes |

## Tool Execution Rules

Hard rules:

```text
1. Browser never executes provider tools directly.
2. Agent Studio owns credentials.
3. Write tools require approval.
4. High-risk conversation blocks autonomous live writes.
5. Dry-run is default until provider writes are explicitly enabled.
6. Every tool plan and result is audited.
7. Tool output must be clipped and redacted before entering diagnostics.
```

## MCP Boundary

Create:

```text
agent-studio/agent_studio/mcp_gateway.py
```

Sprint 3 should not build a full MCP marketplace. It should prepare the boundary.

Correct architecture:

```text
MCP Client / Future Host
-> Sagad MCP Gateway
-> Agent Studio Tool Registry
-> Tool Policy Evaluator
-> Provider Adapter
-> Audit Log
```

Wrong architecture:

```text
LLM -> raw MCP server -> provider API
```

## MCP Exposure Policy

Only expose tools that are:

```text
enabled
server-side
schema-defined
policy-wrapped
auditable
dry-run safe or approval-gated
```

Do not expose:

```text
raw provider credentials
browser-only calls
unscoped filesystem tools
arbitrary shell execution
unreviewed marketplace tools
write tools without explicit approval path
```

## Sprint 3 Demo

Message:

```text
Where is my order? My email is john@example.com.
```

Expected flow:

```text
classified as order_status/account_support
routed to Support Agent
retrieval finds order-status SOP
skill planner requests crm.lookup_contact
policy allows read tool if configured or dry-runs if not
agent drafts verification-safe response
confidence accounts for account-specific risk
HITL required if account-specific details are involved
```

## Exit Gate

Sprint 3 is done when the system can show:

```text
Tool requested
Tool allowed/blocked
Why allowed/blocked
Dry-run/live status
Approval requirement
Tool result
Audit trail
```

If a tool cannot be explained, it should not execute.
