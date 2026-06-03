# Sagad OS Backend Contracts

## Status

v1 uses typed local mocks by default and can optionally read the Agent Studio dev-preview API when `SAGAD_API_BASE_URL` is configured.

This document defines the active preview seam and the future production seam so UI work can avoid hardcoding assumptions.

## v1 Rule

Do not call directly from the browser:

- generic webhook targets;
- Supabase;
- MCP servers;
- authentication providers;
- live CRM APIs;
- Twenty CRM.

Do not add secrets to v1. The frontend may use `SAGAD_API_BASE_URL` to read the server-side Agent Studio preview API. All Chatwoot credentials, Twenty CRM keys, generic webhook secrets, LangSmith keys, and future tool credentials belong in Agent Studio environment variables.

## Future Backend Direction

The future backend is expected to be Agent Studio, a Python LangGraph service behind a stable API boundary. It should own:

- state graphs;
- typed conversation state;
- routing and triage;
- approvals;
- tool-call planning;
- memory policy;
- audit records;
- handoffs;
- LangSmith trace metadata.

Agent Studio state should be strict and typed. Graph nodes should return partial state updates instead of mutating broad untyped objects, so routing, approvals, tool plans, audit entries, and handoffs remain explicit.

The Next.js frontend should consume stable API responses from that service once the backend exists.

## First Live-Preview Contract

The first Agent Studio dev preview exposes these endpoints:

```text
GET  /health
GET  /integrations
GET  /integrations/twenty/health
POST /webhooks/chatwoot
GET  /conversations
GET  /conversations/{id}
POST /conversations/{id}/approve-send
WS   /ws/conversations
POST /tools/crm/lookup-contact
POST /tools/crm/create-note
POST /tools/crm/create-task
POST /tools/crm/update-lead-stage
```

`POST /webhooks/chatwoot` receives a Chatwoot message payload, normalizes the inbound message, classifies intent and risk, retrieves Markdown KB/SOP/QA/compliance context, drafts a reply, runs QA/compliance checks, and stores the conversation as `needs_approval`. One Chatwoot `conversation.id` maps to one Sagad conversation row. New inbound messages append to that thread, regenerate the draft, and reset approval to `needs_approval`. Duplicate webhook retries with the same Chatwoot message id are ignored.

`POST /conversations/{id}/approve-send` is the only outbound path. It sends to Chatwoot only after HITL approval. When Chatwoot credentials are missing in dev, it returns a `dry_run` send status.

`WS /ws/conversations` emits org-scoped realtime events such as `conversation.upserted`, `conversation.message_appended`, `approval.updated`, and `heartbeat`. Browser clients must connect using a short-lived token from the Next.js preview proxy, not provider credentials.

Twenty CRM endpoints are server-side Agent Studio tool endpoints. Reads are unavailable until `TWENTY_ENABLED`, `TWENTY_BASE_URL`, and `TWENTY_API_KEY` are configured. Writes require an explicit supervisor approval payload. Live writes additionally require `TWENTY_DRY_RUN=false` and `TWENTY_ALLOW_WRITES=true`.

The frontend uses `SAGAD_API_BASE_URL` to read this contract and falls back to local mocks when the backend is not configured or unavailable.

### Next.js Preview Proxy

The console posts approvals through its own server route so browser components never hold Chatwoot credentials:

```text
POST /api/conversations/{id}/approve-send
  -> Agent Studio /conversations/{id}/approve-send
```

This route is only active when `SAGAD_API_BASE_URL` is configured.

The console also exposes:

```text
GET /api/realtime-token
  -> signed short-lived token for Agent Studio /ws/conversations
```

This route is active only for authenticated users and only when `SAGAD_WS_PUBLIC_URL` and `SAGAD_REALTIME_SECRET` are configured.

### Conversation Preview Shape

```ts
type AgentStudioConversationDto = {
  id: string;
  chatwoot_conversation_id: string | null;
  chatwoot_message_id: string | null;
  customer_name: string;
  channel: "chatwoot";
  incoming_message: string;
  intent: string;
  risk_level: "low" | "medium" | "high";
  retrieved_knowledge: Array<{
    id: string;
    title: string;
    category: string;
    source_path: string;
    score: number;
    excerpt: string;
  }>;
  crm_context: CrmContactContextDto | null;
  tool_plans: ToolPlanDto[];
  tool_results: ToolResultDto[];
  draft_reply: string;
  compliance_status: "pass" | "needs_review" | "blocked";
  approval_status: string;
  send_status: string;
  trace_url: string | null;
  messages: Array<{
    id: string;
    sender_type: "customer" | "ai_agent" | "human_agent" | "system" | "tool";
    body: string;
    external_message_id: string | null;
    provider: string | null;
    payload: Record<string, unknown>;
    created_at: string;
  }>;
};
```

```ts
type CrmContactContextDto = {
  provider: "Twenty CRM";
  status:
    | "ready"
    | "disabled"
    | "unconfigured"
    | "dry_run"
    | "planned"
    | "error"
    | "blocked";
  contact_id: string | null;
  display_name: string | null;
  company_name: string | null;
  phone_masked: string | null;
  email_masked: string | null;
  lead_stage: string | null;
  notes: string[];
  tasks: string[];
  service_history: string[];
};
```

## Future Tool Layer Direction

The tool layer starts with first-party Agent Studio adapters, including Chatwoot, Twenty CRM, and generic webhook connectors. Future MCP servers can sit behind the same backend boundary for generic CRM, inbox, knowledge, webhook, and internal-system tools.

The frontend should show:

- proposed tool actions;
- required approval state;
- action result summaries;
- audit timeline entries.

The frontend should not hold credentials for tool execution.

## Suggested Future API Shapes

These shapes are planning references only. They are not implemented in v1.

### Queue Response

```ts
type QueueItemDto = {
  id: string;
  customerName: string;
  serviceCategory: string;
  channel: "sms" | "call" | "email" | "web" | "chat";
  intent: string;
  priority: "low" | "normal" | "high" | "urgent";
  slaState: "healthy" | "watch" | "at_risk" | "breached";
  aiConfidence: number;
  stage: string;
  assignedTo: string | null;
  updatedAt: string;
};
```

### Conversation Detail Response

```ts
type ConversationDetailDto = {
  id: string;
  queueItem: QueueItemDto;
  summary: string;
  escalationReason: string | null;
  events: ConversationEventDto[];
  suggestions: AiSuggestionDto[];
};
```

### AI Suggestion Response

```ts
type AiSuggestionDto = {
  id: string;
  type: "reply" | "task" | "crm_note" | "schedule" | "handoff";
  title: string;
  body: string;
  confidence: number;
  approvalState: "not_required" | "needs_approval" | "approved" | "rejected";
  toolPlan: ToolPlanDto | null;
};
```

### Tool Plan Response

```ts
type ToolPlanDto = {
  id: string;
  toolName: string;
  description: string;
  inputPreview: Record<string, string | number | boolean | null>;
  riskLevel: "low" | "medium" | "high";
  requiresApproval: boolean;
};
```

### Tool Result Response

```ts
type ToolResultDto = {
  id: string;
  planId: string;
  provider: string;
  toolName: string;
  status: "planned" | "dry_run" | "blocked" | "succeeded" | "failed";
  detail: string;
  externalId: string | null;
};
```

## Approval Model

Future backend actions should separate suggestion, approval, execution, and audit.

```text
AI suggests action
  |
  v
Supervisor reviews
  |
  +--> reject with reason
  |
  +--> approve
          |
          v
       backend executes tool
          |
          v
       audit event recorded
```

v1 may simulate this flow locally, but it must not execute live actions.

## Mock Data Guidance

Mocks should be close to future contracts while remaining local and deterministic.

Use:

- fake IDs;
- fake customer names;
- fake service requests;
- fake timestamps;
- explicit simulated state.

Avoid:

- real phone numbers;
- real addresses;
- real customer notes;
- environment-specific URLs;
- provider-specific credential names unless documenting future intent.

## Integration Readiness Checklist

Before adding a real backend, confirm:

- the user approves moving beyond typed mocks;
- authentication and authorization requirements are defined;
- audit logging requirements are defined;
- tool approval policy is documented;
- data retention expectations are documented;
- frontend DTOs are versioned or stable enough for integration;
- failure and retry states are represented in the UI.
