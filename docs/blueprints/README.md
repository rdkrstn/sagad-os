# Sagad OS Blueprints

Sagad OS is the learning and build blueprint for the next version of The System: an open-source, self-hostable AI contact-center operating layer for performance, power, expert handling, and skillful execution. The goal is not to build another chatbot or another CRM. The goal is to study, design, and then implement a supervised AI operations loop that can classify inbound conversations, route them to specialist agents, draft replies, apply risk controls, involve humans when needed, and leave an auditable trace.

Sagad OS does not replace every tool. It coordinates external tools through Agent Studio adapters. Chatwoot, Twenty CRM, LangSmith, generic webhooks, and future MCP servers remain connected systems.

These blueprints are intentionally architecture-first. They document the product shape before implementation so the prototype can stay focused around LangGraph, LangChain, LangSmith, Chatwoot, governed knowledge, and HITL operations.

## Blueprint Set

- [01 - Platform Architecture](./01-platform-architecture.md): the end-to-end Sagad runtime, diagrams, and core system layers.
- [02 - Industries Served](./02-industries-served.md): industry playbooks for service businesses, retail, SaaS, BPO, telco, insurance, and finance.
- [03 - AI Contact Center Operating Model](./03-ai-contact-center-operating-model.md): BPO-inspired operating model, agent roles, supervisors, contact drivers, SOPs, QA, and escalation rules.
- [04 - Level 1 Service Business MVP](./04-level-1-service-business-mvp.md): the first build target for service businesses.

## Learning Path

1. Prove the core Chatwoot -> Agent Studio -> HITL loop.
2. Keep the router deterministic and let the classifier and specialist agents do the thinking.
3. Add external adapters only after the classify -> route -> draft -> review loop works.
4. Rebuild the durable stateful version in LangGraph.
5. Use LangSmith from the beginning of the LangGraph phase for traces, evaluation, and quality monitoring.

## Product Ladder

| Level | Product Capability | Buyer Value |
| --- | --- | --- |
| Level 1 | AI intake, classification, routing, drafted replies, HITL | Faster response and fewer missed leads |
| Level 2 | CRM-aware agents and contact-driver logs through external adapters | Better follow-up and cleaner customer records |
| Level 3 | AI supervisor pods, confidence/risk controls, SOP checks | Human supervision without raw workflow debugging |
| Level 4 | QA scoring, coaching, and performance analytics | Contact-center style management and improvement |
| Level 5 | Multi-industry AI contact-center operating system | High-volume, governed AI operations |

## First Build Target

The first real MVP is **Level 1 for service businesses**. Service businesses have clearer sales/support ROI and lower compliance burden than telco, insurance, finance, or fraud-heavy accounts. High-risk industries stay in the blueprint as future architecture targets, not the first build.
