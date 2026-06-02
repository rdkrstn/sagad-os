# Repository Guidelines

## Project Structure & Module Organization

This repository contains two active runtime areas:

- `v1/`: Next.js App Router supervisor console for Sagad OS.
- `agent-studio/`: `uv`-managed Python FastAPI and LangGraph preview backend.

Blueprint docs live in `v1/docs/blueprints/`. Agent Studio knowledge packs live in `agent-studio/knowledge/packs/`. Keep generated caches, `.venv/`, `.next/`, and local screenshots out of source changes unless the user asks for them.

## Build, Test, and Development Commands

Run frontend commands from `v1/`:

- `npm install`: install the pinned frontend dependency tree.
- `npm run dev`: run the Sagad console locally.
- `npm run lint`: run ESLint.
- `npm run build`: create a production Next.js build.

Run backend commands from `agent-studio/`:

- `uv sync`: install Python dependencies from `pyproject.toml`.
- `uv run pytest`: run Agent Studio tests.
- `uv run uvicorn agent_studio.main:app --reload --port 8010`: start the dev API.

## Coding Style & Naming Conventions

Frontend code uses TypeScript, React, Tailwind, and explicit interfaces. Do not use TypeScript `any`. Keep route files thin and put reusable panels under `v1/src/components/`, adapters under `v1/src/lib/api/`, domain types under `v1/src/lib/domain/`, and fixtures under `v1/src/lib/mocks/`.

Python code must be strictly typed, PEP 8 compatible, and managed with `uv`. LangGraph nodes must use typed state and return partial state updates. Do not use legacy LangChain `Chain` classes such as `LLMChain` or `RetrievalQA`.

## Testing Guidelines

Use `npm run lint` and `npm run build` for frontend changes. Use `uv run pytest` for Agent Studio changes. Keep tests deterministic by mocking or dry-running external LLM, LangSmith, Chatwoot, CRM, and network calls.

After implementation work, update public docs when behavior, setup, architecture, or integration contracts change. Keep local maintainer memory/status files untracked.

## Commit & Pull Request Guidelines

Use short, imperative commit messages with a clear scope, for example `docs: add blueprint package`, `feat(agent-studio): add chatwoot webhook`, or `ui: add approval queue state`.

Pull requests should include a brief summary, commands run for verification, linked issues or task notes, and screenshots only when UI or notebook output changes.

## Security & Configuration Tips

Sagad OS is its own open-source, self-hostable AI-native BPO platform. Chatwoot handles channel intake and delivery, Agent Studio handles LangGraph/LangChain orchestration, the Supervisor Console handles HITL approval, and LangSmith handles observability and traces.

External tools such as Twenty CRM, Chatwoot, generic webhook targets, LangSmith, future MCP servers, and client-owned internal systems must connect through Agent Studio adapters. n8n is not part of Sagad OS core orchestration.

Use `.env` for local credentials loaded through environment variables. Do not commit API keys, Chatwoot tokens, Twenty CRM keys, LangSmith tokens, customer exports, generated notebooks with secrets, `.venv/`, `.next/`, or local cache files. Agent Studio sends to Chatwoot only through the HITL approval endpoint. Agent Studio owns all Twenty CRM credentials, health checks, writes, approval gates, retries, and audit metadata; frontend browser code must never call Twenty directly.
