# Stack Lock-In Blueprint

## Summary

Sagad OS locks the first durable platform track to Next.js App Router, Auth.js, Sagad-owned Postgres with pgvector, Agent Studio, and server-side Chatwoot and Twenty CRM adapters.

This is a product and architecture constraint, not a claim that every layer is already implemented in the preview. The current console can still run from typed mocks and the optional Agent Studio preview adapter. The lock-in defines the target stack so new work does not drift into browser-direct provider calls, ad hoc orchestration tools, or competing persistence layers.

## Diagram Source

The Mermaid source for this blueprint lives at `diagrams/stack-lock-in.mmd`.

That Mermaid file is the source of truth. Rendered SVG, PNG, and poster images are presentation artifacts:

- Technical SVG: `images/stack-lock-in.svg`
- Technical PNG: `images/stack-lock-in.png`
- Visual poster: `images/stack-lock-in-poster.png`

## Locked Stack

| Layer | Locked Choice | Boundary |
| --- | --- | --- |
| Supervisor console | Next.js App Router | Operator UI, server-side UI APIs, approval proxy, and mock fallback. |
| Console identity | Auth.js | Console sessions, account identity, role checks, and tenant scoping. |
| Sagad data plane | Sagad Postgres with pgvector | Durable tenants, users, conversations, approvals, audit records, knowledge chunks, and embeddings. |
| AI runtime | Agent Studio | FastAPI, LangGraph orchestration, LangChain model calls, policy gates, adapter execution, retries, and trace metadata. |
| Channel adapter | Chatwoot adapter | Inbound conversation normalization and HITL-approved outbound sends. |
| CRM adapter | Twenty CRM adapter | External CRM reads and writes through Agent Studio only, disabled or dry-run until configured. |

## Runtime Responsibilities

- Next.js owns the supervisor workstation experience, authenticated UI routes, server-only data loading, and approval request handoff.
- Auth.js owns console identity and session claims. It does not store provider API keys in the browser and does not authorize external tool calls by itself.
- Sagad Postgres owns durable Sagad state. pgvector indexes governed knowledge embeddings, while Markdown knowledge records remain the reviewed source material.
- Agent Studio owns LangGraph state transitions, classification, retrieval, drafting, QA/compliance checks, tool plans, approval gates, provider credentials, provider health checks, retries, and audit metadata.
- Chatwoot remains the unified inbox and delivery layer. Agent Studio may send to Chatwoot only through the approved HITL endpoint until auto-send is explicitly designed and approved.
- Twenty CRM remains external infrastructure. Browser code must never call Twenty directly.

## Data Flow Contract

1. A customer message enters through Chatwoot.
2. Chatwoot posts the event to the Agent Studio Chatwoot adapter.
3. Agent Studio normalizes the payload into Sagad canonical conversation state.
4. Agent Studio reads governed context from Sagad Postgres and pgvector-backed retrieval.
5. LangGraph nodes classify, route, retrieve, draft, and run QA/compliance checks.
6. The Supervisor Console displays the pending approval through Next.js server-side APIs.
7. A supervisor approves, edits, rejects, or takes over from the console.
8. Next.js hands the decision to Agent Studio.
9. Agent Studio records the decision and sends approved replies through the Chatwoot adapter.
10. CRM updates, notes, tags, tasks, and lifecycle changes go through the Twenty adapter only after policy and approval checks pass.

## Adapter Rules

- LangGraph nodes call Sagad adapter interfaces, not provider SDKs directly.
- Provider credentials live only in server environments controlled by Agent Studio.
- Browser code can read Sagad state through server-side UI APIs, but cannot call Chatwoot, Twenty CRM, generic webhooks, future MCP servers, or client-owned tools directly.
- Every adapter write must carry policy outcome, approval status, actor, trace ID, retry metadata, and provider result.
- Chatwoot and Twenty are first adapter targets, but the adapter shape must stay tool-agnostic enough for future CRM, ticketing, knowledge, webhook, and internal-system connectors.

## Lock-In Guardrails

- Do not add a frontend database SDK, browser-direct Supabase client, browser-direct CRM client, browser-direct Chatwoot client, or hidden provider webhook path to the console.
- Do not move orchestration into Next.js route handlers. Next.js can proxy supervisor decisions, but Agent Studio owns graph execution.
- Do not introduce n8n as core orchestration. Generic webhook targets can connect through Agent Studio adapters after the base loop is proven.
- Do not persist secrets, customer exports, raw provider tokens, or generated trace artifacts in the repo.
- Do not treat pgvector as the knowledge source of truth. It is the retrieval index; governed knowledge records remain reviewable source material.

## Implementation Order

1. Keep the v1 console mock-safe and read-only unless Agent Studio is configured.
2. Stabilize the Chatwoot -> Agent Studio -> HITL approval loop.
3. Add Sagad Postgres schemas for tenants, users, conversations, approvals, audit, knowledge records, chunks, and embeddings.
4. Add Auth.js for console identity and tenant-aware supervisor access.
5. Move preview approval state from mocks into Sagad Postgres through server-side APIs.
6. Enable the Twenty adapter in dry-run mode, then graduate individual write operations behind explicit approvals.
