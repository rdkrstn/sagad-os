# Contributing to Sagad OS

Thanks for helping build Sagad OS. This project is early, so contributions should keep the platform stable, documented, and easy to self-host.

## Development Setup

Read `QUICKSTART.md` first.

Frontend:

```powershell
cd v1
npm install
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

## Contribution Rules

- Keep provider credentials server-side in Agent Studio.
- Do not add browser-direct calls to Chatwoot, Twenty CRM, Uptime Kuma, MCP, LangSmith, or client internal systems.
- Keep external writes behind approval gates.
- Preserve typed frontend contracts and typed Agent Studio state.
- Use `uv` for Python dependencies.
- Avoid deprecated LangChain `Chain` classes.
- Update public docs when behavior, setup, architecture, or integration contracts change.

## Pull Requests

Each pull request should include:

- what changed;
- why it changed;
- verification commands run;
- screenshots for visible UI changes;
- any migration or deployment notes.

Keep pull requests focused. Split unrelated frontend, backend, docs, and deployment changes when possible.
