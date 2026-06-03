# Sagad OS v1 Console

Sagad OS is an open-source, self-hostable AI-native BPO platform. This `v1/` app is the supervisor console preview built with Next.js App Router, TypeScript, and Tailwind. The demo account is a home services operation where supervisors review inbound conversations, monitor AI-assisted work, approve handoffs, and track queue health.

Sagad OS does not replace every tool. It coordinates external systems through Agent Studio adapters. Chatwoot, Twenty CRM, LangSmith, generic webhooks, and future MCP tools stay outside the browser and are called only by Agent Studio.

The console is mock-driven by default. It can optionally read the root Agent Studio dev backend through `SAGAD_API_BASE_URL` for the Chatwoot HITL preview.

## Product Boundary

The v1 console demonstrates the supervisor experience, not the full production automation layer.

In scope:

- supervisor dashboard shell;
- typed mock queues and conversations;
- optional Agent Studio conversation preview data;
- home services demo account data;
- AI suggestion, approval, escalation, and handoff states;
- HITL-only Chatwoot send readiness states.

Out of scope for v1:

- live browser-direct webhooks;
- Supabase persistence;
- MCP server calls;
- authentication and role enforcement;
- real customer data or live CRM mutations.

Agent Studio owns Python LangGraph orchestration, LangChain model/tool/retrieval primitives, Markdown KB/SOP/QA/compliance retrieval, approval state, Chatwoot send policy, LangSmith trace metadata, and server-side tool execution. Twenty CRM is the selected first CRM target, but it is externally hosted and reached only through Agent Studio adapter endpoints.

## Tech Stack

- Next.js App Router
- TypeScript
- Tailwind
- Typed local mocks
- Agent Studio API adapter fallback

Commercial model: free and open-source when self-hosted; paid later for managed hosting, support, implementation, and enterprise operations.

## Local Development

Run commands from this directory:

```powershell
npm install
npm run dev
```

Then open the local URL printed by Next.js, usually `http://localhost:3000`.

`npm run dev` uses webpack because Turbopack can panic on Windows dev cache/project-root resolution. To test Turbopack explicitly, run `npm run dev:turbo`.

To connect the Agent Studio preview:

```powershell
$env:SAGAD_API_BASE_URL="http://127.0.0.1:8010"
npm run dev
```

Useful checks:

```powershell
npm run lint
npm run build
```

## Documentation

- [System Design](docs/system-design.md)
- [UI Design](docs/ui-design.md)
- [Backend Contracts](docs/backend-contracts.md)
- [MCP Study](docs/mcp-study.md)
- [Blueprints](docs/blueprints/README.md)
- [Memory](MEMORY.md)
- [Agent Guidelines](AGENTS.md)

## Implementation Notes

Keep the app honest about its mock status. UI labels can say "suggested", "queued", "drafted", "approved", or "simulated", but should not imply that live actions have been executed.

Use clean Light Ops BPO styling: clear tables, dense but readable panels, practical filters, visible escalation states, and a calm light theme suitable for repeated supervisor work.
