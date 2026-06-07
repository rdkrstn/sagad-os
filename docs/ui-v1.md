# Sagad OS v1.0.0 UI Visibility Guide

Sagad OS v1 is the public-preview supervisor console for AI-native service operations. Its job is to make the supervision loop visible: inbound message, contact driver, CRM/customer context, knowledge retrieval, selected agent, selected skill, graph run, tool and MCP capability usage, draft, policy checks, HITL approval, outbound action, audit log, and trace metadata.

Design source of truth:

- `../brand-suite/` for SagadOS logo and lockup assets.
- `../design-system/SAGADOS_DESIGN_SYSTEM.md` for the black/white identity and green system signal.
- `../design-system/sagados-product-ui-reference-v0.4/` for product UI references.

## Navigation

### Operations

- Command Center
- Review Queue
- Conversations
- Contact Drivers
- Reports

### Agent Studio

- Agents
- Skills
- Graphs
- Tools
- MCP Servers
- Traces

### Knowledge & QA

- Knowledge Base
- Policy & QA
- Evaluations

### Platform

- Adapters
- Settings

Legacy compatibility routes may remain reachable during preview, including `/queue`, `/analytics`, `/workflows`, `/logs`, `/customers`, and `/superadmin`. They should not define the primary operator IA.

## Concept Model

Driver: why the work came in. Examples: refund policy, order status, angry customer, sales sizing.

Agent: who handles the work. Examples: Support Agent, Sales Agent, QA Agent, Escalation Agent.

Skill: reusable capability or playbook that combines instructions, context, knowledge, tools, output format, policy rules, approval rules, and tests.

Tool: callable server-side function or action, such as `crm.lookup_contact`, `knowledge.search`, or `chatwoot.send_message`.

MCP Server: external capability server that exposes tools, resources, or prompts to approved Sagad agents. MCP is shown as preview/planned unless wired behind Agent Studio.

Graph: LangGraph orchestration flow, such as classify -> CRM lookup -> knowledge retrieval -> agent and skill selection -> draft -> QA gate -> approval -> send -> audit.

Trace: developer observability for an agent run, including graph version, model, tool calls, latency, tokens, cost, errors, and LangSmith references.

Audit Event: operator-facing evidence of what happened. Sagad audit is not replaced by LangSmith; both serve different audiences.

## Preview Limits

- `v1` uses deterministic preview fixtures unless `SAGAD_API_BASE_URL` connects Agent Studio.
- Browser code must not call Chatwoot, Twenty, LangSmith, MCP servers, model providers, OCR, or retrieval databases directly.
- Chatwoot sends remain HITL-only.
- Twenty writes remain disabled or approval-gated until backend gates are verified.
- Local-only UI actions must be labeled as preview unless they call an Agent Studio endpoint.

## Connected And Planned

Connected or implemented:

- Next.js v1 shell and Auth.js session boundary.
- Optional Agent Studio API seam through server routes.
- Chatwoot and Twenty configuration contracts.
- Knowledge ingestion UI when Agent Studio is configured.
- Approval-send proxy route.
- Diagnostics and audit projections.

Optional readiness:

- LiteLLM gateway.
- LangSmith trace metadata.

Planned:

- Uptime Kuma.
- MCP/FastMCP capability servers.
- Google Drive, Notion, Confluence, Guru, and website knowledge adapters.
- Production hardening for persisted skills, graph versioning, and evaluations.

## Visual Rules

- Light mode is for review, setup, forms, docs, and long reading.
- Dark mode is for command, infrastructure, dashboard, and terminal-like control surfaces.
- Green is only for active, healthy, connected, ready, selected, or primary action states.
- Logos are monochrome-first and should come from `brand-suite`.
- Cards are for repeated records and metrics, not every section wrapper.
- The AI draft is the primary review object; evidence must sit near it.

## Demo Fixture Rules

Preview fixtures must be deterministic, fake, clearly labeled, and professional. Do not include real customer data, real phone numbers, real addresses, secrets, profanity, or live provider URLs. Northstar Apparel Support is the public-preview demo workspace when live Agent Studio data is not configured.
