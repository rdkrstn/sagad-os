# Approval Queue

Sagad Approvals is the supervisor control point.

> The ticket fields this doc aspired to (assignee, priority, pipeline_stage, SLA,
> ticket_status) are now implemented on every conversation — see
> [`docs/revops-tickets.md`](./revops-tickets.md) for the queue + `PATCH .../ticket` surface.

## When Approval Is Required

- low trust score;
- high-risk refund or cancellation;
- angry customer;
- policy conflict;
- failed tool or send;
- verification needed;
- customer asks for a human;
- missing approved knowledge.

## Supervisor Actions

- approve;
- edit and approve;
- reject;
- escalate;
- take over;
- retry tool.

Every action should create an audit event. High-risk replies should not auto-send.

