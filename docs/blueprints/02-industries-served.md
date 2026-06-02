# Industries Served

Sagad OS can serve multiple industries, but each industry has different risk, verification, agent roles, buyer value, and client-owned tools. The first build target is service businesses because the sales/support loop is easier to prove and less compliance-heavy.

## Industry Matrix

| Industry | Main Buyer Pain | Primary Agents | Verification Need | Risk | MVP Offer |
| --- | --- | --- | --- | --- | --- |
| Service businesses | Missed leads, slow replies, weak follow-up | Sales, support, discovery | Low to medium | Low | AI front desk for sales and support |
| Retail / ecommerce | Repeated order questions, product questions, complaints | Support, sales, returns | Medium | Medium | AI support pod for order and product inquiries |
| SaaS | Tier-1 support load, onboarding friction, tech questions | Support, technical, sales | Medium | Medium | AI technical support and onboarding assistant |
| BPO | QA load, supervisor span, agent inconsistency | Supervisor, QA coach, specialist agents | Depends on account | Medium to high | AI supervisor and QA console |
| Telco | High-volume support, technical issues, billing disputes | Support, technical, retention, fraud | High | High | AI triage and supervised technical support |
| Insurance | Policy questions, claims, sensitive data | Support, claims, retention, fraud/risk | High | High | AI intake and human-reviewed claims support |
| Finance | Account security, disputes, fraud, compliance | Support, fraud/risk, retention | Very high | Very high | AI triage with strict verification and human takeover |

## Service Businesses

**Buyer pain:** leads come from web chat, Facebook, forms, SMS, referrals, and calls, but the team replies slowly or inconsistently. Sales questions and support questions blend together.

**Common contact drivers:**

- pricing inquiry
- service fit
- quote request
- booking request
- timeline question
- support issue
- complaint
- general inquiry

**Agent roles:**

- Sales Agent qualifies interest, explains the offer, asks next-step questions, and prepares follow-up.
- Support Agent handles basic customer issues and asks for verification before account-specific help.
- Discovery Agent handles greetings, vague messages, empty messages, and unclear intent.

**Metrics:** lead response time, qualified leads, booked calls, auto-send rate, HITL rate, missed lead reduction, CSAT, and follow-up completion.

**Why first:** lower compliance risk, easy demo, strong ROI story, and clear buyer language.

## Retail And Ecommerce

**Buyer pain:** customers ask the same questions about availability, orders, returns, warranties, delivery, branches, and product fit.

**Common contact drivers:** product availability, order status, delivery status, return/refund, warranty, branch pickup, product comparison, complaint.

**Agent roles:** Support Agent, Sales Agent, Returns Agent, and Inventory/Order Tooling.

**Verification:** order lookups and refunds require identity or order verification. Product questions can usually be answered without verification.

**Metrics:** ticket deflection, AHT, first contact resolution, return escalation rate, order lookup success, and CSAT.

## SaaS

**Buyer pain:** support teams spend time on onboarding, login issues, feature confusion, billing questions, and repeated docs-based troubleshooting.

**Common contact drivers:** login issue, onboarding help, feature question, bug report, integration issue, billing question, upgrade inquiry.

**Agent roles:** Technical Agent, Support Agent, Sales Agent, Retention Agent.

**Verification:** account and workspace verification before private data, billing, or admin actions.

**Metrics:** tier-1 deflection, activation rate, AHT, bug escalation quality, documentation gaps, churn-risk detection.

## BPO

**Buyer pain:** supervisors and QA teams cannot monitor every conversation deeply. Agents drift from SOPs, QA scoring is slow, and coaching happens after the damage is done.

**Common contact drivers:** account-specific and client-specific. BPO deployments should import the account's driver tree, SOPs, QA rubrics, and escalation rules.

**Agent roles:** AI Supervisor, AI QA Coach, Sales Agent, Support Agent, Technical Agent, Retention Agent, Fraud/Risk Agent.

**Verification:** dictated by the client account. Some accounts need basic account verification; others require strict identity flows.

**Metrics:** CSAT, AHT, SLA hit rate, QA score, transfer rate, escalation rate, supervisor attention load, coaching opportunities, and compliance adherence.

## Telco

**Buyer pain:** very high support volume, device troubleshooting, billing issues, plan changes, retention pressure, and fraud exposure.

**Common contact drivers:** device issue, network outage, billing dispute, plan change, cancellation, SIM/account security, fraud report.

**Agent roles:** Technical Agent, Support Agent, Retention Agent, Fraud/Risk Agent.

**Verification:** high. Account and device verification are required before private account actions.

**Metrics:** AHT, first contact resolution, technician dispatch avoidance, retention saves, fraud escalation accuracy, SLA.

## Insurance

**Buyer pain:** intake is repetitive, claims require process discipline, customers are stressed, and mistakes are expensive.

**Common contact drivers:** policy question, claim intake, document request, payment question, renewal, cancellation, complaint.

**Agent roles:** Support Agent, Claims Intake Agent, Retention Agent, Fraud/Risk Agent.

**Verification:** high. Policy and identity verification are required before personal or claim-specific discussion.

**Metrics:** claim intake completeness, escalation accuracy, compliance adherence, CSAT, AHT, and document collection completion.

## Finance

**Buyer pain:** support volume is high and errors can create financial, regulatory, or security risk.

**Common contact drivers:** transaction dispute, account access, card issue, suspicious activity, payment problem, loan question, account update.

**Agent roles:** Support Agent, Fraud/Risk Agent, Retention Agent, Human Escalation.

**Verification:** very high. Most actions require identity verification and strict audit logs.

**Metrics:** fraud escalation accuracy, false positive rate, compliance adherence, AHT, SLA, CSAT, and human takeover rate.

## Industry Rollout Order

1. Service businesses: easiest to sell, easiest to prove, lowest risk.
2. Retail/ecommerce: strong support deflection and CRM value.
3. SaaS: stronger technical-agent story and KB/RAG value.
4. BPO: stronger supervisor/QA story, but requires account-level process depth.
5. Telco, insurance, finance: high-value future categories with strict verification and compliance requirements.
