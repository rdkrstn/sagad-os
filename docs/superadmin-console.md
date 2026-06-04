# SuperAdmin Console

The SuperAdmin Console is the instance-level control plane for self-hosted Sagad OS operators.

It is separate from the daily AI Ops console:

- the AI Ops console is for exceptions, approvals, QA, knowledge, reports, and live supervisor work;
- the SuperAdmin Console is for workspaces, users, platform apps, runtime health, model gateways, and instance settings.

## Current Scope

The first preview is visibility-first. It shows:

- current workspace and user counts;
- enabled, optional, and planned platform apps;
- Agent Studio runtime health;
- LangGraph app setup for Studio debugging;
- optional LiteLLM gateway readiness;
- persistence and credential boundaries.

## Operator Boundary

Owner/Admin users can configure provider credentials and write policies.

Supervisors and QA users should focus on exception review and redacted readiness, not raw provider secrets.

Integrator users can inspect adapter contracts under `Settings -> Advanced`.

## Non-Goals

This is not a replacement for Chatwoot Super Admin, Twenty admin, Uptime Kuma, LangSmith, or cloud infrastructure dashboards. Sagad OS coordinates those systems through Agent Studio and shows the operational state needed for AI supervision.
