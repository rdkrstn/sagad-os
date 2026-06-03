# Agent Studio

Agent Studio is the Python LangGraph backend preview for Sagad OS. It receives Chatwoot webhook payloads, runs typed LangGraph/LangChain orchestration over Markdown knowledge packs, creates a supervised draft, records trace metadata, and sends approved replies back to Chatwoot.

Agent Studio is also the adapter boundary. External tools such as Twenty CRM, Chatwoot, generic webhook targets, LangSmith, and future MCP servers are never called directly from the browser. n8n is not part of Sagad OS core orchestration.

## Inputs And Outputs

- Input: Chatwoot webhook payloads at `POST /webhooks/chatwoot`.
- Output: conversations, drafts, QA/compliance results, and HITL approval state.
- Output: approved Chatwoot send attempt from `POST /conversations/{id}/approve-send`.
- Output: integration readiness from `GET /integrations`.
- Output: Twenty CRM status from `GET /integrations/twenty/health`.
- Output: realtime conversation events from `WS /ws/conversations`.

Chatwoot threading rule: one Chatwoot `conversation.id` maps to one Sagad conversation. New inbound customer messages append to the thread, regenerate the latest draft, and reset approval to `needs_approval`. Duplicate webhook retries with the same Chatwoot message id are idempotent. Outgoing or private Chatwoot messages are ignored.

## Environment Variables

- `DATABASE_URL`
- `AGENT_STUDIO_INTERNAL_SECRET`
- `SAGAD_REALTIME_SECRET`
- `CHATWOOT_BASE_URL`
- `CHATWOOT_ACCOUNT_ID`
- `CHATWOOT_API_ACCESS_TOKEN`
- `CHATWOOT_WEBHOOK_TOKEN`
- `TWENTY_ENABLED`
- `TWENTY_BASE_URL`
- `TWENTY_API_KEY`
- `TWENTY_API_MODE`
- `TWENTY_DRY_RUN`
- `TWENTY_ALLOW_WRITES`
- `TWENTY_TIMEOUT_SECONDS`
- `LANGSMITH_TRACING`
- `LANGSMITH_API_KEY`
- `LANGSMITH_PROJECT`
- `OPENAI_API_KEY`
- `OPENAI_MODEL`
- `OPENAI_EMBEDDING_MODEL`

OpenAI and LangSmith variables are optional in this deterministic dev preview. Chatwoot send runs as `dry_run` when Chatwoot credentials are not set. Twenty CRM is disabled and dry-run by default; live writes require `TWENTY_ENABLED=true`, `TWENTY_DRY_RUN=false`, `TWENTY_ALLOW_WRITES=true`, and an explicit supervisor approval payload.

`DATABASE_URL` is optional. When unset, Agent Studio uses the in-memory development store. When set to a Postgres-compatible URL, Agent Studio runs SQL migrations from `migrations/`, enables the Sagad schema foundation, and stores conversations, inbound messages, approvals, CRM tool plans, CRM tool results, and audit events through `psycopg`. `AGENT_STUDIO_INTERNAL_SECRET` protects privileged console-to-Agent-Studio routes when configured. `SAGAD_REALTIME_SECRET` verifies short-lived WebSocket tokens minted by the console.

When `DATABASE_URL` is set, Agent Studio also syncs Markdown knowledge records into Postgres and uses pgvector-backed retrieval with deterministic local dev embeddings. Production retrieval should replace those dev embeddings with real embedding generation and evaluation.

## Commands

```powershell
uv sync
uv run pytest
uv run uvicorn agent_studio.main:app --reload --port 8010
```

## LangSmith Studio / LangGraph Visual Debugging

Agent Studio includes `langgraph.json` so the official LangSmith Studio can inspect and run the local graph visually. This is for graph debugging and workflow design. The Sagad Console remains the supervisor operations UI.

Use Python 3.12 for this workflow. The repo includes `.python-version` because current LangGraph Studio dev dependencies can fail under Python 3.14 native builds.

```powershell
Copy-Item .env.example .env
$env:PYTHONUTF8 = "1"
uv sync --dev
uv run langgraph dev
```

The graph is exposed as:

```text
sagad_conversation -> ./agent_studio/graph.py:graph
```

After `langgraph dev` starts, open the Studio URL printed by the CLI. It should look similar to:

```text
https://smith.langchain.com/studio/?baseUrl=http://127.0.0.1:2024
```

On Windows, keep `PYTHONUTF8=1` set when using the LangGraph CLI. Some CLI help output contains Unicode characters that can fail under the default PowerShell code page.

Health check:

```powershell
Invoke-WebRequest -UseBasicParsing http://127.0.0.1:8010/health
Invoke-WebRequest -UseBasicParsing http://127.0.0.1:8010/integrations
Invoke-WebRequest -UseBasicParsing http://127.0.0.1:8010/integrations/twenty/health
```

See [Twenty External VPS](docs/twenty-external-vps.md) for the CRM hosting boundary.
