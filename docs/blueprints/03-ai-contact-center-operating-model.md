# AI Contact Center Operating Model

Sagad borrows from BPO and contact-center operations. The product is not just a reply generator. It is an operating system for supervising AI agents as they handle customer conversations inside role, process, and risk boundaries.

## Operating Hierarchy

```text
Client Account
-> AI Supervisor Pod
-> AI QA / Coach Layer
-> Specialist AI Agents
-> Customer Conversations
-> CRM / Knowledge / SOP Systems
```

The AI Supervisor Pod monitors the agent team. The QA/Coach layer checks process adherence and drafts feedback. Specialist agents handle conversations. Humans step in when risk, confidence, policy, or customer context requires it.

## Specialist Agent Roles

| Agent | Scope | Verification | Typical Handoff |
| --- | --- | --- | --- |
| Sales Agent | Rapport, qualification, pricing questions, demos, quotes, next steps, and lead probing | Usually none unless accessing account data | Support, human sales |
| Support Agent | Account/service issues, complaints, general help | Account verification before private actions | Technical, retention, fraud, human |
| Technical Agent | Device, app, setup, integration, bug, troubleshooting | Device/environment verification; account verification when needed | Support, engineering, human |
| Retention Agent | Cancellation, churn, objections, save offers | Account verification and policy bounds | Human retention, support |
| Fraud/Risk Agent | Suspicious activity, disputes, security, sensitive claims | Strict identity verification | Human fraud/risk team |

Agents should not share one giant prompt. Each agent needs a scoped role, allowed tools, allowed knowledge, escalation rules, and prohibited actions.

## Contact Drivers

Contact drivers answer the operational question: **why did the customer contact us?**

Examples:

| Domain | Driver | Sub-driver |
| --- | --- | --- |
| Sales | pricing_inquiry | package_price |
| Sales | quote_request | custom_scope |
| Support | account_access | login_issue |
| Support | billing_refund | duplicate_charge |
| Technical | device_issue | app_version_error |
| Retention | cancellation | price_objection |
| Fraud | suspicious_activity | unauthorized_login |
| Support | unclear_need | greeting_only |

Each conversation should store:

```text
intent
route
contact_driver
sub_driver
confidence
risk_level
sentiment
verification_required
assigned_agent
assigned_ai_supervisor
sla_status
aht_timer
resolution_status
disposition
```

## Knowledge, SOP, And QA Layers

| Layer | Purpose | Examples |
| --- | --- | --- |
| Knowledge Base | Gives factual answer context | FAQs, product pages, policy summaries, help docs |
| SOPs | Defines required process | refund process, verification script, escalation policy |
| QA Rubrics | Scores the interaction | greeting, empathy, verification, accuracy, resolution |
| CRM Context | Gives customer history | contact profile, tags, notes, lifecycle stage, prior conversations |
| Tool Layer | Lets agents act | search contact, create task, add note, update lead stage |

The agent should draft from knowledge. The supervisor should check SOP and risk. QA should score after the interaction or at review time.

## Supervisor Alerts

An AI agent should ping its supervisor when:

- confidence is below threshold
- risk is medium or high
- customer sentiment turns negative
- the contact driver requires verification
- the customer asks for refunds, cancellation, account access, fraud, legal, medical, or financial help
- a tool call fails
- retrieved knowledge conflicts
- the drafted reply violates an SOP or guardrail
- SLA or AHT is close to breach
- the customer asks for a human

## Human-In-The-Loop Decisions

| Condition | Decision |
| --- | --- |
| High confidence + low risk | Eligible for faster approval; auto-send only after account policy explicitly allows it |
| Medium confidence + low risk | Human approval or lightweight review |
| Low confidence | One sales/support probing question or human review |
| High risk | Human takeover |
| Verification required but missing | Ask verification question, do not perform private action |
| Tool failure | Safe fallback and supervisor alert |
| SOP conflict | Block auto-send and request review |

## Dashboard Model

The console should be organized around **supervisor attention**, not raw messages.

```text
Command Center
-> Supervisor Pods
-> Attention Queue
-> Conversation Review
-> Agent Performance
-> Driver Analytics
-> SOP / KB / QA Settings
```

Minimum low-fi review panel:

```text
Customer Message
AI Draft
Intent
Route
Contact Driver
Confidence
Risk
Verification Requirement
SOP Used
CRM Context
LangSmith Trace Link
Actions: Approve, Edit, Reject, Coach, Take Over
```

## Metrics

**BPO metrics:**

- CSAT
- AHT
- SLA hit rate
- first contact resolution
- transfer rate
- escalation rate
- QA score
- reopen rate

**AI metrics:**

- confidence score
- auto-send eligibility or policy-send rate
- HITL approval rate
- human takeover rate
- draft edit rate
- rejected draft rate
- routing accuracy
- tool failure rate
- guardrail trigger rate
- SOP adherence
- LangSmith evaluation score

## Operating Principle

Sagad OS should make AI agents manageable the way a BPO supervisor manages human agents: by watching drivers, queues, adherence, performance, risk, and customer outcomes. The product value is supervision, process control, adapter governance, and traceability, not just text generation.
