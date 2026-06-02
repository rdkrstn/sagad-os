# Repository Guidelines

## Product Context

Sagad OS is an open-source, self-hostable AI operations platform. The `v1/` application is the supervisor console preview for a home services demo account. It should feel like a clean Light Ops BPO supervisor console: operational, calm, dense enough for repeated use, and focused on queue supervision rather than marketing.

The default v1 slice uses typed mocks. The only approved live-preview seam is the optional server-side `SAGAD_API_BASE_URL` adapter to Agent Studio. Do not add live browser-direct webhooks, Supabase, MCP server calls, authentication, persistence, browser-direct tool calls, or production secrets in v1.

Backend work belongs in Agent Studio: a Python LangGraph service that owns orchestration, policy, approvals, audit, retrieval, and server-side tool execution. Future MCP access must sit behind Agent Studio, not behind direct browser calls.

Sagad OS does not replace every tool. It coordinates external systems through Agent Studio adapters. Chatwoot is the channel intake and delivery layer. Twenty CRM, LangSmith, generic webhook targets, future MCP tools, and client-owned internal tools are connected systems, not owned subsystems.

## Project Structure

- `src/app/`: Next.js App Router routes and route-level UI.
- `src/components/`: reusable UI components.
- `src/lib/`: typed mock data, view models, helpers, and constants.
- `public/`: static assets.
- `docs/`: product, UI, backend, and research documentation.
- `docs/blueprints/`: Sagad architecture, knowledge, Chatwoot HITL, and phase diagrams.

Keep route files thin. Move reusable console panels, status chips, timeline rows, mock datasets, and derived metrics into named modules as they stabilize.

## Build, Test, and Development Commands

Run commands from `v1/`.

- `npm install`: install dependencies from `package-lock.json`.
- `npm run dev`: run the local Next.js dev server.
- `npm run build`: create a production build.
- `npm run lint`: run the configured lint command.

If a command is missing or fails because the script is not configured, document the gap in the final report instead of inventing a parallel toolchain.

## Coding Style

Use TypeScript, React, Next.js App Router, and Tailwind. Prefer typed mock objects and explicit union types for statuses, channels, intents, priorities, and tool names. Do not use `any` in TypeScript.

Use ASCII only in source and docs. Use concise operational copy. Avoid public-marketing language inside the console. Do not present unsupported AI behavior as live or autonomous.

## Future Agent Studio Standards

These standards apply to the root `agent-studio/` preview backend and all future backend work.

- Use Python 3.12+ managed with `uv` only. Do not add pip, Poetry, Conda, or ad hoc virtualenv workflows.
- Build orchestration with LangGraph State Graph and LangChain v0.3+ primitives.
- Do not use old LangChain `Chain` classes or legacy chain-style orchestration.
- Define strict typed graph state with explicit schemas for messages, routing decisions, approvals, tool plans, and audit events.
- Use partial state updates from graph nodes; do not mutate shared state implicitly.
- Keep Twenty CRM, Chatwoot, and other external systems behind server-side Agent Studio tools with policy, approval, and audit controls.
- Treat Twenty CRM as externally hosted infrastructure. Store `TWENTY_*` values only in Agent Studio environments, never in browser code.
- Keep Chatwoot outbound sends HITL-only until the user explicitly approves auto-send behavior.
- Use LangSmith traces for graph runs, tool calls, approval decisions, and failure analysis.

## UI Standards

The interface should read as a supervisor workstation for home services operations. Prioritize:

- queue health, SLA risk, handoff status, and escalation clarity;
- compact tables, timelines, filters, segmented controls, and detail panes;
- clear distinction between AI suggestions, human approvals, and completed actions;
- restrained light theme styling with accessible contrast.

Do not build a landing page for the app shell. The first screen should be the usable supervisor console.

## Testing Guidelines

No formal test suite is required for every documentation-only change. For UI or logic changes, add focused tests when the touched behavior is shared, stateful, or easy to regress. Mock external services and keep tests deterministic.

For frontend verification, prefer `npm run lint`, `npm run build`, and browser inspection of the changed route when feasible.

## Security And Configuration

Do not commit API keys, tokens, customer exports, auth secrets, Supabase credentials, webhook URLs, LangSmith keys, or real customer data. Use fake home services demo data only.

v1 must not include:

- live backend writes;
- live CRM mutations;
- hidden auth assumptions;
- real phone numbers or customer addresses;
- secrets in `.env`, docs, screenshots, or mock data.

The optional Agent Studio adapter may read preview conversations and display approval state, knowledge context, QA/compliance gates, and dry-run send status. It must fall back to mocks when `SAGAD_API_BASE_URL` is unset or unavailable.

After implementation work, update public docs when behavior, setup, architecture, or integration contracts change. Keep local maintainer memory/status files untracked.

## Multi-Agent Ownership

Other agents may edit other files. Do not revert unrelated changes. Before editing, inspect the target files you own. Keep changes inside the assigned ownership scope unless the user explicitly expands it.

If future work requires code changes outside the current scope, report the needed files and wait for permission.
