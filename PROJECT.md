# Project: Sagad OS — Sprint 5 Features

## Architecture

Sagad OS is a monorepo with two runtime areas:

- **agent-studio/** — Python FastAPI + LangGraph backend (uv-managed)
  - `agent_studio/agents.py` — AgentConfig + AgentRegistry (scans .md files)
  - `agent_studio/graph.py` — LangGraph graph with draft_reply node (currently uses litellm.completion)
  - `agent_studio/config.py` — Settings with env var config
  - `agent_studio/main.py` — FastAPI app with all endpoints
  - `agent_studio/state.py` — AgentStudioState TypedDict
  - `agent_studio/schemas.py` — Pydantic models
  - `agent_studio/store.py` — In-memory conversation store
  - `tests/test_agents.py` — Existing agent tests

- **v1/** — Next.js App Router supervisor console
  - `v1/src/app/agents/page.tsx` — Agents page (calls getAgents, renders AgentsConsole)
  - `v1/src/components/agent-studio/agent-studio-console.tsx` — AgentsConsole component
  - `v1/src/components/conversations/conversation-review.tsx` — Conversation review with draft textarea
  - `v1/src/lib/api/index.ts` — fetchAgentStudioJson and helpers
  - `v1/src/lib/api/sagad-api.ts` — getAgents and other data fetchers
  - `v1/src/components/ui/` — Shared UI components (Dialog, Input, Textarea, etc.)

## Milestones

| # | Name | Scope | Dependencies | Status |
|---|------|-------|-------------|--------|
| 1 | Dynamic Agent CRUD | Backend CRUD endpoints + frontend Create/Edit/Delete UI | none | PLANNED |
| 2 | LangChain ChatOpenAI Refactor | Replace litellm.completion with ChatOpenAI in graph.py | none | PLANNED |
| 3 | Streaming Draft Generation | SSE endpoint + Regenerate button in frontend | M2 | PLANNED |

## Interface Contracts

### M1: Agent CRUD API
- `POST /agents` — Create agent, body: `{ id, name, intents, allowed_tools, system_prompt }`
- `PUT /agents/{agent_id}` — Update agent
- `DELETE /agents/{agent_id}` — Delete agent
- All persist to `.md` files in `agent_studio/agents/` and reload registry

### M2: ChatOpenAI in draft_reply
- `ChatOpenAI(model=..., base_url=..., api_key=...)` with `.bind_tools()`
- Config: `LITELLM_MODEL`, `OPENROUTER_API_KEY` in Settings
- No signature change to `draft_reply(state) -> dict`

### M3: Streaming SSE
- `GET /conversations/{conversation_id}/draft/stream` → `text/event-stream`
- SSE format: `data: <token>\n\n`, final `data: [DONE]\n\n`
- Frontend: fetch with ReadableStream, update textarea progressively
- On complete: save aggregated draft to conversation record

## Code Layout
- Backend changes: `agent_studio/agents.py`, `agent_studio/graph.py`, `agent_studio/config.py`, `agent_studio/main.py`, `pyproject.toml`
- Backend tests: `tests/test_agents.py`
- Frontend changes: `v1/src/app/agents/page.tsx`, `v1/src/components/agent-studio/agent-studio-console.tsx`, `v1/src/components/conversations/conversation-review.tsx`, `v1/src/lib/api/index.ts` or `sagad-api.ts`
- Config: `agent-studio/.env.example`

## Verification
- Backend: `uv run pytest` from `agent-studio/`
- Frontend: `npm run lint` and `npm run build` from `v1/`
