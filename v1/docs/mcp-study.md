# Sagad OS MCP Study

## Purpose

This study records how MCP could fit into Sagad OS after the Chatwoot HITL preview and the first direct Agent Studio adapters. MCP is not implemented in v1. The current dashboard uses typed mocks by default and may read Agent Studio preview data through `SAGAD_API_BASE_URL`.

## What MCP Would Do

MCP servers would provide a standard tool layer for CRM-like operations. Instead of building one-off frontend integrations, Agent Studio calls adapters and future MCP tools through controlled server-side policies.

Useful generic CRM tool categories:

- contact lookup;
- conversation history lookup;
- deal or job stage update;
- task creation;
- note logging;
- appointment lookup;
- appointment creation request;
- invoice or quote lookup;
- follow-up reminder creation;
- message draft handoff.

## Proposed Boundary

```text
Next.js Console
  |
  v
Agent Studio
  |
  v
MCP Client Runtime
  |
  v
MCP Servers For CRM Tools
```

The browser should never call MCP servers directly. MCP belongs behind Agent Studio, where server-side policy, approval, audit, identity, rate limits, and tool input validation can be enforced.

Twenty CRM, Chatwoot, generic webhooks, and internal client tools should route through Agent Studio policy and approval gates. Agent Studio should record audit events and LangSmith traces for proposed tool plans, approved executions, denials, failures, and retries.

Twenty CRM is currently treated as an external provider. It is reached through the Agent Studio Twenty adapter first; future MCP facades can wrap the same operations after the direct Chatwoot and Twenty preview loops are proven.

## Why Not Direct Frontend MCP

Direct browser-to-tool execution would create problems:

- secrets and credentials could leak;
- tool permissions would be hard to enforce;
- audit logs could be bypassed;
- supervisor approvals could be skipped;
- CRM writes could happen without backend policy;
- retries and partial failures would be difficult to coordinate.

For Sagad, MCP belongs behind Agent Studio.

## Tool Approval Policy

Future MCP-backed actions should be classified by risk.

Low risk:

- read contact;
- read recent conversation;
- read job status;
- draft internal note.

Medium risk:

- create task;
- log note;
- update non-critical metadata;
- draft customer reply for approval.

High risk:

- send customer message;
- change appointment time;
- change job stage;
- update invoice or payment status;
- close or cancel a job.

High-risk actions should require explicit supervisor approval through Agent Studio before any MCP-backed execution.

## Example Future Tool Manifests

These examples are conceptual only.

```text
crm.contacts.search
crm.contacts.get
crm.conversations.list
crm.jobs.update_stage
crm.tasks.create
crm.notes.create
crm.appointments.request_reschedule
crm.messages.draft_reply
```

## UI Implications

The console should eventually show tool plans before execution:

- tool name;
- plain-English purpose;
- input preview;
- risk level;
- approval requirement;
- expected result;
- execution status;
- audit event.

In v1, these should be mocked as simulated tool plans.

## Home Services Examples

Example simulated tool plans:

- create a dispatcher task for an urgent no-cool HVAC request;
- draft a reply asking for preferred appointment windows;
- log a CRM note summarizing a missed call;
- flag a quote follow-up as overdue;
- request supervisor approval before changing a booking time.

## Open Questions For Future Work

- Which client CRM or field-service system follows Twenty CRM as the next adapter?
- Which actions can AI propose but never execute?
- Which actions can execute after supervisor approval?
- What audit trail is required for customer-facing actions?
- How should failed tool calls appear in the supervisor timeline?
- What tenant and role model controls tool availability?

## v1 Instruction

Keep MCP references educational and forward-looking. Do not add MCP packages, servers, clients, credentials, endpoints, or live tool calls in the v1 console.

## Current Preview Boundary

The Chatwoot HITL preview does not implement MCP yet. Agent Studio calls Chatwoot directly through a small server-side adapter so the inbound webhook and approved-send loop can be proven first.

After that loop works, Chatwoot and Twenty actions can move behind MCP-style tool facades such as `chatwoot.messages.send_approved`, `crm.contacts.search`, and `crm.notes.create`. The browser still calls only Sagad OS routes.
