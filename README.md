# Sagad OS v1

Sagad OS is an open-source, self-hostable AI-native BPO platform. Chatwoot handles channel intake, Agent Studio handles LangGraph/LangChain orchestration, the Supervisor Console handles HITL approval, and LangSmith handles observability.

The current project contains:

- `v1/`: Next.js supervisor console preview for a home services account.
- `agent-studio/`: `uv`-managed FastAPI + LangGraph backend preview.
- `docs/blueprints/`: canonical architecture and operating model docs.

Start with `QUICKSTART.md` for the technical guide: architecture, repo layout, local setup, environment variables, API endpoints, and integration boundaries.

Contributor docs:

- `CONTRIBUTING.md`
- `SECURITY.md`
- `docs/CI-CD.md`
- `docs/VERSIONING.md`
- `docs/DEPLOYMENT.md`

Sagad OS does not replace every tool. Chatwoot, Twenty CRM, LangSmith, generic webhooks, and future MCP servers stay external or adapter-governed. Agent Studio owns credentials, policies, approvals, retries, audit logs, and trace metadata. n8n is not part of Sagad OS core orchestration.

## Local Checks

Frontend:

```powershell
cd v1
npm run lint
npx tsc --noEmit --pretty false
npm run build
```

Backend:

```powershell
cd agent-studio
uv sync
uv run pytest
```

Container smoke test:

```powershell
docker compose -f compose.preview.yaml build
```

Self-hosting is the open-source path. Paid commercial work can later focus on managed hosting, implementation, support, and enterprise operations.

## Documentation

Project documentation is plain Markdown. Use `QUICKSTART.md` for technical onboarding and `docs/blueprints/` for architecture context. Local maintainer notes such as status, task, focus, and memory files are intentionally ignored by Git.
