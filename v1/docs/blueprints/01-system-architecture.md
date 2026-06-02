# System Architecture Blueprint

## Summary

Sagad OS is the open-source AI operations layer for BPO-style teams. It sits above client channels and tools, runs typed Agent Studio workflows, retrieves governed knowledge, routes work to supervisors, and only sends live replies after approval.

![Sagad Architecture Poster](images/sagad-architecture-poster.png)

## Canonical Reference Architecture

This is the source-of-truth structure for docs, UI copy, memory updates, and implementation plans.

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

![Canonical Architecture Diagram](images/canonical-architecture.png)

## Working Preview Architecture

```mermaid
flowchart TD
  Chatwoot["Chatwoot VPS"] --> Webhook["POST /webhooks/chatwoot"]
  Webhook --> Studio["Agent Studio API"]
  Studio --> State["Typed LangGraph State"]
  State --> Classifier["Classifier Node"]
  Classifier --> Retriever["Policy-Aware Retriever"]
  Retriever --> KB["Markdown KB/SOP/QA/Compliance Pack"]
  Retriever --> Vector["In-Memory Vector Store"]
  Vector --> Draft["Draft Reply Node"]
  Draft --> Guardrails["QA + Compliance Check"]
  Guardrails --> Console["Sagad OS Console"]
  Console --> Approval["HITL Approve Send"]
  Approval --> Send["POST /conversations/{id}/approve-send"]
  Send --> Chatwoot
  Studio --> LangSmith["LangSmith Traces"]
```

![Working Preview Diagram](images/working-preview.png)

## Responsibilities

- Chatwoot owns live web chat intake and delivery.
- Agent Studio owns LangGraph/LangChain orchestration, normalization, classification, retrieval, drafting, QA/compliance checks, approval state, and outbound send policy.
- Sagad OS Console owns queue visibility, review, and supervisor approval.
- Twenty CRM stays external and is reached only through Agent Studio adapter endpoints.
- Generic webhooks can connect external apps later through Agent Studio policy gates.
- Markdown knowledge packs are the first source of truth for KB, SOPs, QA, compliance, escalations, and approved templates.
- LangSmith is optional in dev and records traces when configured.

## Non-Goals

- No auto-send in the first live loop.
- No browser-direct Twenty, Chatwoot, webhook target, MCP, or internal-system calls.
- No MCP server until the adapter boundary is proven.
- No production auth or persistent audit store in the first preview.
