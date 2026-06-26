# RevOps Tickets

Lightweight ticketing on top of conversations — every conversation **is** a ticket. There is
no separate ticket table: `ConversationRecord` carries the ticket fields, the queue is a
filtered `GET /conversations`, and a supervisor mutates a ticket with
`PATCH /conversations/{id}/ticket`. Implementation: `agent_studio/agent_studio/main.py`
(`update_conversation_ticket`, `list_conversations`), `agent_studio/store.py`
(`update_ticket`, `list` with ticket filters), `agent_studio/schemas.py`
(`TicketUpdateRequest`, `TicketStatus`, `TicketPriority`). Tests:
`agent-studio/tests/test_tickets.py`. Migration: `migrations/0008_tickets_revops.sql`.

This keeps the RevOps "definition of done" honest: ticket state lives on the same record the
webhook/poller pipeline writes, so an inbound message and its ticket are never out of sync.

## Ticket fields on `ConversationRecord`

| Field | Type | Default | Notes |
|---|---|---|---|
| `ticket_status` | `TicketStatus` | `open` | `open` · `in_progress` · `waiting` · `resolved`. CHECK-constrained in Postgres. |
| `assignee` | `str \| None` | `None` | Supervisor/user id owning the ticket. |
| `priority` | `TicketPriority \| None` | `None` | `low` · `medium` · `high` · `urgent`. CHECK-constrained. |
| `pipeline_stage` | `str \| None` | `None` | Free-form RevOps stage (e.g. `triage`, `negotiation`). |
| `sla_due_at` | `datetime \| None` | `None` | SLA deadline (UTC). |
| `provider_conversation_id` | `str \| None` | `None` | GHL conversation id (also drives the poller watermark mapping + GHL approve-send dispatch). |

Defaults keep existing rows unchanged (`ticket_status='open'`, everything else NULL), so
prior behavior and tests are preserved.

**Inbound re-saves never clobber ticket state.** The inbound pipeline only writes
message/intent/draft fields; it never manages tickets (only the PATCH endpoint does, via
`update_ticket`). In `store.save`, a fresh record with default ticket fields preserves the
existing assignment (`ticket_status`/`assignee`/`priority`/`pipeline_stage`/`sla_due_at`
are copied from the prior record). The Postgres store mirrors this: ticket columns are
absent from the `ON CONFLICT DO UPDATE` set. So a customer's follow-up message can never
silently reset a supervisor's assignment.

## Queue — `GET /conversations`

`list_conversations` accepts query params that map to SQL `WHERE` clauses backed by the
`conversations_ticket_queue_idx` index `(organization_id, ticket_status, assignee, updated_at DESC)`:

| Query param | Matches |
|---|---|
| `ticket_status` | exact `ticket_status` |
| `assignee` | exact `assignee` |
| `priority` | exact `priority` |

Params compose. Without any, the queue returns all conversations newest-first. Examples:

- `GET /conversations?ticket_status=in_progress` — the "in-triage" lane.
- `GET /conversations?assignee=e2e-supervisor` — a supervisor's personal queue.
- `GET /conversations?ticket_status=open&priority=high` — high-priority unowned work.

## `PATCH /conversations/{conversation_id}/ticket`

Internal-secret-gated (`x-sagad-internal-secret`, mirrors the other protected endpoints) and
requires supervisor approval. Body — `TicketUpdateRequest`, all fields optional (a field is
left unchanged when omitted):

```json
{
  "assignee": "e2e-supervisor",
  "priority": "high",
  "ticket_status": "in_progress",
  "pipeline_stage": "triage",
  "sla_due_at": "2026-07-01T12:00:00Z",
  "supervisor_id": "e2e-supervisor"
}
```

Flow: `store.get` → 404 if missing → `store.update_ticket` (mutates + sets `updated_at`) →
audit → broadcast → return the updated record.

- **Validation:** `ticket_status` / `priority` are validated against the `TicketStatus` /
  `TicketPriority` literals (and the DB CHECK constraints on write).
- **Audit:** a `ticket.updated` diagnostic event is recorded with the new
  `ticket_status`/`assignee`/`priority`/`pipeline_stage`, `actor_type="user"`, and
  `actor_id={supervisor_id}`. Visible at `GET /diagnostics/events`.
- **Realtime:** the update is broadcast over the realtime channel so the console queue
  updates live.

## Audit via diagnostics

Ticket mutations are observable through the same diagnostic-event stream as the rest of the
pipeline (`docs/audit-log.md`):

| `event_type` | When |
|---|---|
| `ticket.updated` | A supervisor PATCHed ticket fields. |
| `ghl.poller.duplicate_skipped` | The poller skipped an already-recorded message. |
| `ghl.poller.rate_limited` | The poller hit a GHL 429 and is backing off. |
| `ghl.poller.db_not_ready` | The poller skipped a cycle because the DB wasn't ready. |
| `ghl.poller.cycle_failed` | A poller cycle raised; backing off with exponential backoff. |

## E2E coverage

`scripts/dev_e2e.py` exercises the ticket surface end-to-end on real Postgres: a GHL
conversation defaults to `ticket_status=open`; a PATCH sets
`assignee`/`priority`/`ticket_status=in_progress`; the queue filters
(`?ticket_status=in_progress`, `?assignee=…`) include the conversation; a fresh `GET`
confirms the assignment persisted. This is part of the `scripts/dev-e2e.sh` `ALL GREEN`
definition of done.