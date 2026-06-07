# Sagad OS UI Design

## Design Intent

Sagad OS should feel like a compact product console for AI customer operations. The interface is for repeated operational use: scanning queues, spotting risk, reviewing AI work, approving next steps, and handing off exceptions.

The UI should make the platform boundary clear: Sagad OS coordinates external systems through Agent Studio adapters. Chatwoot, Twenty CRM, LangSmith, generic webhooks, and future MCP tools are connected providers, not built-in subsystems.

Do not build a landing page. The first screen should be the working dashboard.

## Visual Direction

Use the local product UI reference in `../../design-system/sagados-product-ui-reference-v0.4` as the source of truth for visual direction.

- black and white identity;
- paper/white surfaces for light-mode review and long reading;
- black/graphite surfaces for dark-mode infrastructure and control;
- green only for active, healthy, connected, ready, and primary action states;
- semantic warning, danger, and info colors only when they communicate status;
- no purple gradients, AI sparkles, decorative blobs, or oversized hero sections.

The UI should look calm, inspectable, organized, and practical.

## Layout Principles

Prioritize a supervisor workflow:

- top-level queue health and SLA summary;
- filterable work queue;
- selected conversation or case detail;
- AI recommendations and approval controls;
- timeline of customer and system events;
- visible escalation reasons.

Preferred patterns:

- tables for queues;
- tabs for major views;
- segmented controls for work modes;
- compact cards for repeated metrics;
- side panels for details;
- status chips for state;
- icon buttons for common tools when icons are available.

Avoid cards inside cards. Avoid large marketing-style sections.

## Information Hierarchy

The supervisor should see these signals quickly:

1. Which work is at risk.
2. Why it is at risk.
3. What the AI recommends.
4. What action needs human approval.
5. What has already happened.

Use concise labels:

- `Needs Review`
- `AI Draft`
- `SLA Risk`
- `Escalated`
- `Ready To Approve`
- `Waiting On Customer`
- `Tech Scheduling`
- `Quote Follow-Up`

## Console Areas

### App Shell

The app shell uses a compact grouped sidebar, 56px topbar, brand-suite SagadOS mark, workspace/environment status, theme toggle, alerts, and user menu. Logo assets come from `brand-suite`; green variants are reserved for active/system moments.

Top-level navigation:

- Operations: `Command Center`, `Review Queue`, `Conversations`, `Contact Drivers`, `Reports`
- Agent Studio: `Agents`, `Skills`, `Graphs`, `Tools`, `MCP Servers`, `Traces`
- Knowledge & QA: `Knowledge Base`, `Policy & QA`, `Evaluations`
- Platform: `Adapters`, `Settings`
- `Settings`

### Metrics Row

Show operational metrics such as:

- open conversations;
- SLA at risk;
- AI drafts waiting;
- escalations;
- appointments to schedule;
- follow-ups due.

### Queue

The queue should support scanning. Include customer, intent, channel, service type, age, priority, AI confidence, owner, and current stage when available.

### Detail Pane

The detail pane should explain one selected work item. It should include:

- customer and service context;
- timeline;
- AI summary;
- suggested next action;
- approval state;
- escalation reason.

### AI Review Panel

AI suggestions must read as assistive, not autonomous. Use copy such as `Suggested reply`, `Recommended next step`, and `Needs supervisor approval`.

Do not imply that a message, CRM update, invoice, or booking was actually sent in v1 unless Agent Studio reports the action. Twenty CRM should read as external and dry-run/disabled by default.

## Interaction States

Frontend-only interactions can simulate:

- selecting a queue item;
- filtering by priority or status;
- approving a draft locally;
- marking a mock item reviewed;
- expanding timeline events;
- switching tabs.

These states should not persist beyond the local session unless a future approved storage layer is added.

## Accessibility

- Keep contrast readable on light backgrounds.
- Do not rely on color alone for risk states.
- Keep text inside buttons and chips short enough to fit.
- Use semantic headings and controls.
- Make focus and hover states visible.

## Content Style

Use operational language. Avoid hype.

Good:

- `3 drafts need approval`
- `Low confidence: missing service date`
- `Escalate to dispatcher`
- `Simulated CRM note`

Avoid:

- `Autopilot growth engine`
- `Fully automated customer success`
- `AI has completed the workflow`
- `Twenty write dry-run`

## Demo Account Voice

Use home services examples. Keep customer details fake and generic. Prefer operational specificity without private data:

- clogged kitchen sink;
- no-cool HVAC request;
- recurring cleaning quote;
- pest control follow-up;
- electrical outlet repair;
- appliance repair scheduling.
