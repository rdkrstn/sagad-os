# Approval Queue

Sagad Approvals is the supervisor control point.

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

