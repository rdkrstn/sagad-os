# Getting Started

Sagad OS is a self-hostable AI operations platform for BPO, agency, and service operations teams. It starts with a seeded demo workspace so contributors can see the operating loop without bringing their own data.

## First Run

```powershell
cd v1
npm install
npm run dev
```

Then open `http://localhost:3000`.

The console ships with `Sagad Demo Operations` demo data:

- sample Chatwoot-style conversations;
- Twenty CRM-style customer context;
- approved SOP and FAQ references;
- AI-drafted replies;
- approval states;
- audit trail events;
- basic AI Ops metrics.

## Backend Preview

```powershell
cd agent-studio
uv sync
uv run pytest
uv run uvicorn agent_studio.main:app --reload --port 8010
```

Useful endpoints:

- `GET /health`
- `GET /health/live`
- `GET /health/ready`
- `GET /integrations`
- `GET /integrations/litellm/health`
- `GET /conversations`
- `POST /webhooks/chatwoot`
- `POST /conversations/{id}/approve-send`

## Admin Surfaces

The daily console is for AI Ops supervisors. The profile menu includes the SuperAdmin Console for instance health, workspace/user visibility, platform apps, LangGraph app setup, and optional LiteLLM gateway status.

Use the docs below when configuring those layers:

- `docs/superadmin-console.md`
- `docs/litellm-gateway.md`

## Mental Model

Sagad OS coordinates tools; it does not replace every tool. Chatwoot receives messages, Agent Studio runs orchestration and adapters, the Console handles supervisor approval, and Sagad Audit records the decision trail.
