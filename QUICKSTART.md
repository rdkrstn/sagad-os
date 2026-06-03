# Sagad OS Technical Quickstart

Last updated: 2026-06-04

Sagad OS is an open-source, self-hostable AI operations platform for AI-native BPO and contact-center workflows. It coordinates external tools instead of replacing them.

## Platform Overview

Sagad OS has three core runtime surfaces:

- `v1/`: Next.js supervisor console for queues, approvals, conversations, agent performance, contact drivers, knowledge, QA, the operator/admin Integrations page, and settings.
- `agent-studio/`: Python FastAPI + LangGraph backend preview for orchestration, typed state, adapter policy, tool planning, HITL gates, and approved sends.
- `docs/blueprints/`: architecture docs, diagrams, and implementation phases.

External systems connect through Agent Studio adapters:

- Chatwoot handles channel intake and approved customer replies.
- Twenty CRM is the first external CRM adapter target and starts read-only.
- Uptime Kuma provides infrastructure health later.
- LangSmith provides traces and observability.
- FastMCP/MCP is a future tool exposure layer behind Agent Studio.

Browser code must not call Chatwoot, Twenty, Uptime Kuma, LangSmith, MCP, or client internal systems directly.

The console direction follows the SagadOS Premium Open Ops design system: calm, modular, inspectable, transparent, and operator-focused. The UI should show routes, states, modules, logs, docs, and configuration without AI-magic framing.

The Integrations page is operator/admin-facing: Owner and Admin users can set up and test Chatwoot/Twenty connections, while Supervisor users can monitor redacted readiness and health. Developer payloads, DTO contracts, and webhook/tool examples belong under `Settings -> Advanced`.

## Prerequisites

- Node.js and npm for the Next.js console.
- Python 3.12+ for Agent Studio.
- `uv` for Python dependency management.
- Docker if you want the bundled Sagad Postgres/pgvector preview database.
- Optional external services for live integration work: Chatwoot, Twenty CRM, LangSmith, and Uptime Kuma.

## Repository Layout

```text
.
|-- v1/                 # Next.js supervisor console
|-- agent-studio/       # FastAPI + LangGraph backend preview
|-- docs/blueprints/    # Canonical architecture and study docs
|-- docs/CI-CD.md       # CI and future CD model
|-- docs/DEPLOYMENT.md  # container and VPS deployment notes
|-- docs/VERSIONING.md  # release/versioning policy
|-- README.md           # Project overview
|-- QUICKSTART.md       # Technical quickstart
|-- CONTRIBUTING.md     # contributor workflow
|-- SECURITY.md         # security policy
|-- compose.preview.yaml
|-- compose.vps.example.yaml # Example NPM/shared-network VPS compose
```

## Run The Frontend

From `v1/`:

```powershell
npm install
npm run dev
```

The default console dev script uses webpack for local stability. Turbopack remains available with `npm run dev:turbo` from `v1/`.

Verification commands:

```powershell
npm run lint
npx tsc --noEmit --pretty false
npm run build
```

The console uses typed mock data by default. It can read Agent Studio through `SAGAD_API_BASE_URL`. Auth.js is wired for email magic-link sessions when `DATABASE_URL`, `AUTH_SECRET`, `AUTH_URL`, `EMAIL_SERVER`, and `EMAIL_FROM` are configured. Google OAuth appears on the sign-in page when `AUTH_GOOGLE_ID` and `AUTH_GOOGLE_SECRET` are set.

## Run Agent Studio

From `agent-studio/`:

```powershell
uv sync
uv run pytest
uv run uvicorn agent_studio.main:app --reload --port 8010
```

Useful dev endpoints:

- `GET /health`
- `GET /integrations`
- `GET /integrations/twenty/health`
- `GET /integration-configs`
- `PUT /integration-configs/{provider}`
- `POST /integration-configs/{provider}/disable`
- `POST /integration-configs/{provider}/test`
- `POST /webhooks/chatwoot`
- `GET /conversations`
- `GET /conversations/{id}`
- `POST /conversations/{id}/approve-send`
- `WS /ws/conversations`

## Open The Graph In LangSmith Studio

Agent Studio has a `langgraph.json` file that exposes the local graph to the official LangSmith Studio visual debugger.

From `agent-studio/`:

```powershell
Copy-Item .env.example .env
$env:PYTHONUTF8 = "1"
uv sync --dev
uv run langgraph dev
```

Open the Studio URL printed by the CLI. It usually points to LangSmith Studio with `baseUrl=http://127.0.0.1:2024`.

Use Studio to inspect graph state, run nodes, debug transitions, and test the local `sagad_conversation` graph. Use the Sagad Console for supervisor operations and HITL review. Current local Studio dev should use Python 3.12; `.python-version` pins that for `uv`.

On Windows, keep `PYTHONUTF8=1` set for LangGraph CLI commands to avoid PowerShell code page errors when the CLI prints Unicode help text.

## Run With Docker

From the repository root:

```powershell
docker compose -f compose.preview.yaml build
docker compose -f compose.preview.yaml up -d
```

The preview compose file starts:

- Sagad Console on port `3000`.
- Agent Studio on port `8010`.
- Sagad Postgres/pgvector on host port `5433`.

For a VPS that already uses Nginx Proxy Manager on an external Docker network, copy the example to a local ignored compose file:

```bash
cp .env.example .env
cp compose.vps.example.yaml compose.vps.yaml
# Edit .env and compose.vps.yaml for the target VPS.
docker compose -f compose.vps.yaml up -d --build
```

The local `compose.vps.yaml` file is ignored by Git so each VPS can adjust names, networks, and ports. The example does not bind host port `3000`. Nginx Proxy Manager should route to `sagad-console:3000` on the shared `client_internal_network`.

## Environment Configuration

Use environment variables for service bootstrap credentials. Do not commit secrets.

Live Chatwoot and Twenty connection setup should be saved through Agent Studio. When `DATABASE_URL` is configured, Agent Studio stores connection metadata in Sagad Postgres and stores provider tokens/API keys as encrypted secret versions. Browser code receives only redacted status, missing-field, dry-run, and write-gate fields.

Frontend:

- `SAGAD_API_BASE_URL`
- `SAGAD_WS_PUBLIC_URL`
- `SAGAD_REALTIME_SECRET`
- `DATABASE_URL`
- `AUTH_SECRET`
- `AUTH_URL`
- `EMAIL_SERVER`
- `EMAIL_FROM`
- `AUTH_GOOGLE_ID`
- `AUTH_GOOGLE_SECRET`
- `AGENT_STUDIO_INTERNAL_SECRET`

Agent Studio:

- `DATABASE_URL`
- `AGENT_STUDIO_INTERNAL_SECRET`
- `SAGAD_REALTIME_SECRET`
- `SAGAD_INTEGRATION_ENCRYPTION_KEY`
- `OPENAI_API_KEY`
- `OPENAI_MODEL`
- `OPENAI_EMBEDDING_MODEL`
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

`SAGAD_INTEGRATION_ENCRYPTION_KEY` should be a strong deployment secret. In local development, Agent Studio can fall back to the internal secret or a local default, but production deployments must provide a durable encryption key before saving provider credentials.

## Current Integration Path

Owners and Admins configure Chatwoot and Twenty from the operator/admin Integrations page. Supervisors monitor connection status and readiness without edit access. Developer-oriented request payloads, DTO contracts, headers, and tool samples are documented under `Settings -> Advanced` and backend contract docs rather than shown as the main integrations experience.

The first live slice is:

```text
Chatwoot inbound message
-> Agent Studio webhook
-> one Sagad thread per Chatwoot conversation
-> LangGraph typed state
-> knowledge retrieval and draft
-> Supervisor Console approval
-> approved reply back to Chatwoot
-> optional approval-gated CRM note plan
```

Repeated customer messages in the same Chatwoot session append to the same Sagad conversation and regenerate the latest supervised draft. The console live-sync chip uses `SAGAD_WS_PUBLIC_URL` plus short-lived tokens signed with `SAGAD_REALTIME_SECRET` to refresh on Agent Studio WebSocket events.

Twenty CRM starts read-only. Writes remain disabled or dry-run until approval gates and write-policy tests are verified.

## Development Rules

- Keep provider credentials server-side in Agent Studio.
- Keep LangGraph nodes calling internal adapter services, not provider SDKs directly.
- Use typed state and partial state updates in LangGraph nodes.
- Do not use legacy LangChain `Chain` classes.
- Add FastMCP only after adapter boundaries are stable.
- Preserve mock fallback behavior in the frontend until live APIs are explicitly enabled.
- Keep Integrations focused on operator/admin monitor and setup; keep developer payload/contracts under `Settings -> Advanced`.
- Update public docs when behavior, setup, architecture, or integration contracts change.

## CI And Versioning

- CI workflow: `.github/workflows/ci.yml`
- Version policy: `docs/VERSIONING.md`
- Deployment notes: `docs/DEPLOYMENT.md`
- Current version: `VERSION`

## Maintainer Workflow

Keep public documentation focused on setup, architecture, interfaces, and contribution rules. Local maintainer notes, working status, task lists, and personal knowledge-management files should stay untracked.
