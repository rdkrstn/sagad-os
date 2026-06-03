# Sagad OS System Design

## Summary

Sagad OS is an open-source, self-hostable AI-native BPO platform. The `v1/` console is the first supervisor UI and opens as an empty Johnred Workspace until Agent Studio provides live data or an explicit demo fixture is enabled. It is built as a Next.js App Router application with TypeScript, Tailwind, typed local mocks, Auth.js session handling, and an optional Agent Studio dev-preview adapter.

Sagad OS does not replace every tool. It coordinates Chatwoot, Twenty CRM, LangSmith, generic webhooks, future MCP servers, and client internal systems through Agent Studio adapter boundaries.

The console direction follows the SagadOS Premium Open Ops design system: open-source infrastructure, self-hosted ownership, visible structure, modular panels, status rows, clear borders, and restrained navy/teal accents. It should feel calm and inspectable for operators while staying technical enough for admins and builders.

## System Boundary

v1 runs in the Next.js frontend runtime. By default it uses local mocks. When `SAGAD_API_BASE_URL` is configured, server-rendered routes may read the root Agent Studio preview API.

Included:

- App Router pages and layouts;
- React components;
- Tailwind styling;
- TypeScript domain types;
- local mock datasets;
- simulated UI state;
- optional read-only Agent Studio preview data;
- operator/admin Integrations page state from Agent Studio;
- `Settings -> Advanced` views for developer payloads, DTO contracts, headers, and tool samples.

Excluded from the v1 console:

- browser-direct webhook execution;
- browser-direct provider setup or provider API calls;
- Supabase persistence;
- production LangGraph automation beyond Agent Studio preview reads;
- MCP server calls;
- production-grade organization and role administration;
- real customer data;
- production telemetry.

## Conceptual Architecture

The full visual blueprint package lives in `docs/blueprints/`. It is the source for the Chatwoot HITL preview, knowledge architecture, and implementation phase diagrams.

```text
User
  |
  v
Next.js App Router
  |
  v
Supervisor Console UI
  |
  v
Typed Mock Data And View Models
```

Future architecture target:

```mermaid
flowchart LR
  Channels["Channel Intake: Web Chat / Email / WhatsApp / SMS / Social"]
  Chatwoot["Chatwoot: Unified Inbox"]
  Studio["Agent Studio: AI Orchestration"]
  Policy["Routing & Policy Engine"]
  Knowledge["Governed Knowledge Layer: KB / SOPs / QA / Compliance"]
  Console["Supervisor Console: HITL"]
  External["External Systems: CRM / Ticketing / Calendar / Payments / Identity / APIs"]
  Observability["Observability & Traces: LangSmith"]
  Outcomes["Outcomes: Faster Resolution / Quality / Oversight"]

  Channels --> Chatwoot
  Chatwoot --> Studio
  Studio --> Policy
  Knowledge --> Studio
  Studio --> Console
  Console --> Chatwoot
  Studio --> External
  Observability --> Studio
  Observability --> Console
  Console --> Outcomes
```

Agent Studio is the orchestration layer between the Next.js console and external systems. It owns the Python LangGraph runtime, LangChain model/tool/retrieval primitives, typed state, agent routing, policy checks, approval handling, tool planning, credentials, retries, audit, and LangSmith trace metadata. Twenty CRM is the selected first CRM target, but it is hosted outside Sagad OS. Future MCP/FastMCP belongs behind Agent Studio adapters, not beside the browser.

The v1 Integrations page is the operator/admin monitor and setup surface. Owner and Admin users can configure and test Chatwoot/Twenty connections through Agent Studio. Supervisor users see redacted readiness, missing-field, health, dry-run, and write-gate state only. Developer payloads and contract examples belong under `Settings -> Advanced` so the main integrations page stays operational and inspectable.

## Working Preview Path

The first dev preview connects Chatwoot to Agent Studio, with Twenty CRM exposed as a disabled/dry-run external adapter. Connection setup is stored through Agent Studio; provider secrets are encrypted in Sagad Postgres when persistence is configured:

```text
Chatwoot webhook
  -> Agent Studio FastAPI endpoint
  -> typed LangGraph workflow
  -> Markdown KB/SOP/QA/compliance retrieval
  -> draft reply and QA/compliance gate
  -> Sagad OS Console approval queue
  -> approved Chatwoot reply
```

The frontend reads Agent Studio only when `SAGAD_API_BASE_URL` is set. Without that variable, it uses local typed mocks.

## Core Domains

### Queue

The queue represents conversations or work items that need supervisor awareness. Items should expose:

- customer name;
- service category;
- channel;
- priority;
- SLA status;
- AI confidence;
- assigned owner;
- current stage;
- next recommended action.

### Conversation

The conversation view shows a timeline of inbound customer messages, AI drafts, tool suggestions, supervisor approvals, and handoffs. v1 should make it obvious which events are mock or simulated.

When Agent Studio is configured, `GET /conversations/{id}` returns the ordered `messages` array that the console should render as the source of truth. A Chatwoot session should appear as one Sagad thread, not repeated conversation rows. Realtime events from `WS /ws/conversations` only trigger a server refresh through the console live-sync chip; browser code still never calls Chatwoot or privileged provider routes directly.

### AI Work Review

AI work is advisory in v1. Suggested replies, next-best actions, call summaries, and routing decisions require supervisor interpretation. Do not present AI actions as autonomous live execution.

### Approval And Escalation

Approvals are local UI states in v1. Escalations should explain why the work item needs attention, such as low confidence, overdue SLA, angry customer language, missing appointment data, or payment risk.

## Data Model Direction

Use TypeScript types before data is used by the UI. Favor narrow union types over loose strings.

Suggested domains:

- `QueueItem`
- `ConversationEvent`
- `AiSuggestion`
- `ApprovalState`
- `ServiceCategory`
- `CustomerIntent`
- `SupervisorAction`
- `SlaState`
- `Channel`

## Empty Workspace Preview

The default console workspace is Johnred Workspace. It should start empty until Agent Studio receives live Chatwoot conversations, trusted CRM context, knowledge retrieval results, or configured agent/pod records.

Use fake records only when building explicit demos or tests. Do not include real addresses, phone numbers, customer names, or private operational data in committed fixtures.

## Runtime Decisions

- Keep v1 state local.
- Keep mocks deterministic.
- Keep route-level components thin.
- Keep integration seams documented but inactive.
- Keep Agent Studio optional through `SAGAD_API_BASE_URL` with mock fallback.
- Keep Twenty CRM and Chatwoot external; Sagad OS stores connection metadata and encrypted secret versions through Agent Studio, not in browser code.
- Keep Integrations focused on operator/admin monitor and setup and move developer payload/contracts to `Settings -> Advanced`.
- Follow the SagadOS design system for console direction: modular cards, visible workflow states, code/docs panels for technical surfaces, white panels on warm off-white backgrounds, teal only for active/connected states, and green only for success/healthy state.
- Treat webhooks as generic connector primitives, not n8n-specific orchestration.
- Prefer clear supervisor workflow over broad feature coverage.

## Non-Goals

- production backend design;
- database schema implementation;
- production-grade organization, invite, and role management;
- live automation execution;
- CRM-specific integration logic;
- analytics instrumentation;
- mobile-first field technician experience.

## Verification Expectations

For documentation-only changes, review the changed files for ASCII, scope, and consistency.

For UI changes, run:

```powershell
npm run lint
npm run build
```

When the route is changed, inspect the rendered app in a browser and verify that it still reads as Premium Open Ops infrastructure: calm, transparent, modular, and operator/admin focused rather than a landing page or generic AI product.
