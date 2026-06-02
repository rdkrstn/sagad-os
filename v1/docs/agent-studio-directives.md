# Senior System Architect Directives: Agent Studio

## Purpose

Agent Studio is the Python backend workbench for Sagad OS agents. It is used to design, inspect, and operate LangGraph and LangChain agent flows, including approval gates, retrieval, tool calls, adapters, and LangSmith trace review.

This file defines architecture and implementation expectations for the root `agent-studio/` backend and later production hardening.

## Runtime Rules

- Strictly use `uv` for Python dependency management, locking, and execution.
- Never invoke native `pip` or standard `venv` activation scripts manually.
- Target Python 3.12 or newer.
- Build backend orchestration around LangGraph State Graph architecture.
- Use LangChain v0.3 or newer only.
- Build any frontend surface with Next.js App Router, React, TypeScript, and Tailwind.
- Treat Twenty CRM as the first open-source CRM integration target, hosted externally from Sagad OS.
- Treat Chatwoot as the webhook and conversational API integration target.
- Treat webhooks as generic connector primitives, not n8n-specific orchestration.
- Use LangSmith for targeted telemetry through environment variables.
- Load all Twenty CRM, Chatwoot, and LangSmith configuration through environment variables.

## Structural And Code Quality Rules

- Do not use old Chain classes such as `LLMChain` or `RetrievalQA`.
- Do not use deprecated LangChain patterns.
- LCEL pipe composition is acceptable only where it is native to the selected LangChain API.
- Define explicit typed state with `TypedDict` or Pydantic models.
- LangGraph nodes must return partial state updates.
- Nodes must not mutate global state directly.
- Use strict Python type hints for all public functions, graph nodes, tool adapters, and service boundaries.
- Define explicit TypeScript interfaces for frontend data contracts.
- Do not use TypeScript `any`.

## Implementation Protocol

1. Plan first: output a brief conceptual plan and do not output code blocks until the plan is accepted.
2. Execute after acceptance: write clean, modular code blocks or files that follow the approved plan.
3. Map the architecture: provide an inline Mermaid graph detailing data flow or state changes.
4. Document after implementation: append concise markdown covering system inputs and outputs, crucial environment variables, and verification commands or testing steps.
5. Keep docs aligned with actual runtime behavior after each accepted implementation phase.

## Current Preview Boundary

- Agent Studio lives at root `agent-studio/` as a `uv` Python project.
- FastAPI exposes health, integration status, Chatwoot webhook, conversation list/detail, approve-send, and CRM tool endpoints.
- LangGraph owns normalize, classify, retrieve, draft, and QA/compliance nodes.
- Markdown knowledge packs are the first KB/SOP/QA/compliance source.
- Retrieval is in-memory dev only.
- Outbound Chatwoot sends are HITL-only and dry-run when credentials are missing.
- MCP, auth, persistent audit storage, and production hardening remain future phases. Twenty CRM is present only as a disabled/dry-run external adapter until credentials and approval gates are explicitly enabled.

The first knowledge source is Markdown under the Agent Studio knowledge pack. The first vector retrieval path is in-memory dev only.

## Preview Endpoints

```text
GET  /health
GET  /integrations
GET  /integrations/twenty/health
POST /webhooks/chatwoot
GET  /conversations
GET  /conversations/{id}
POST /conversations/{id}/approve-send
POST /tools/crm/lookup-contact
POST /tools/crm/create-note
POST /tools/crm/create-task
POST /tools/crm/update-lead-stage
```
