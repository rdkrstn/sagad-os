# GoHighLevel (GHL) Adapter

GHL integration via the universal webhook pipeline (`POST /webhooks/ghl`). Implementation:
`agent_studio/agent_studio/adapters/ghl.py`. Tests: `agent-studio/tests/test_ghl_adapter.py`.

## Inbound

GHL Workflow/Custom Webhook delivers a message event to `POST /webhooks/ghl`. The adapter:

1. **Verifies** the HMAC-SHA256 of the **raw request body** with `GHL_WEBHOOK_SECRET`,
   compared in constant time against the `X-GHL-Signature` header (also accepts
   `Webhook-Signature` / `X-Signature`). Missing/invalid → 401. **No secret configured →
   verification is a no-op (dev/test)** — set `GHL_WEBHOOK_SECRET` in production.
2. **Normalizes** the payload to `NormalizedInbound`. GHL does not publish one canonical
   inbound shape (it is workflow-configurable), so `normalize()` reads defensively across
   common key paths:

   | Field | Read from (in order) |
   |---|---|
   | `provider_conversation_id` | `conversationId` · `conversation.id` |
   | `provider_message_id` | `message.id` · `messageId` |
   | `message_text` | `message.body` · `message.text` · `body` · `messageBody` |
   | `customer_name` | `contact.name` · `contact.firstName` · `contactName` · `"GHL contact"` |
   | `channel` | `message.type` · `channel` · `"ghl"` |
   | `event_type` | `type` |
   | `extra.location_id` | `locationId` · `location.id` |

3. **Ignores** outbound echoes: `message.direction` in `{outbound, sent, outgoing}` or
   `event_type` in `{outboundmessage, outbound}` → `202` (not an inbound customer message).

A worked fixture shape (matches `scripts/dev_e2e.py`):
```json
{
  "type": "InboundMessage",
  "conversationId": "e2e-conv-1",
  "locationId": "loc-e2e",
  "message": {"id": "e2e-msg-1", "body": "Hi, what is your pricing for a tune-up?", "direction": "inbound", "type": "SMS"},
  "contact": {"id": "cont-e2e", "name": "E2E GHL Customer"}
}
```

## Outbound

An approved/auto reply is sent back through `send_outbound`. Mode is selected by
`GHL_OUTBOUND_MODE` (per-adapter config):

### `webhook` (live)
POST to `{GHL_BASE_URL}/conversations/{conversationId}/messages` with
`Authorization: Bearer {GHL_API_KEY}`, `Version: 2021-04-15`, and body
`{"type": "SMS", "message": reply}`. On success → `status=sent` with `external_id`; on
timeout/request error → `status=failed` with `error_type`; on non-2xx → `status=failed`
with `http_status`. `GHL_DRY_RUN=true` short-circuits to `status=dry_run` (no network call).

### `mcp` (descriptor-only — honest dry-run)
**There is no MCP execution runtime.** The Agent Studio MCP gateway (`mcp_gateway.py`) is
descriptor-only by design: it builds redacted tool descriptors and exposes no provider
credentials or execution surface. So `mcp` mode returns an **honest dry-run** that names
the descriptor the supervisor *would* invoke (`mcp://ghl.messages.send?conversationId=…`)
rather than fabricating a send. To send live today, set `GHL_OUTBOUND_MODE=webhook`. A real
MCP executor (MCP-client dependency + server config + approval-gated invocation) is a
tracked follow-up, intentionally not faked here.

## Auto-send gate

The draft auto-sends only when `compliance == "pass"` AND `risk == "low"` AND
`confidence >= 0.88` AND the draft is non-empty. Otherwise the conversation is
`needs_approval` / `not_sent` and a human approves from the console.

## Configuration

| Env | Default | Purpose |
|---|---|---|
| `GHL_WEBHOOK_SECRET` | _(empty)_ | HMAC secret for inbound verification. Empty = no-op (dev). |
| `GHL_API_KEY` | _(empty)_ | Bearer token for outbound webhook sends. |
| `GHL_LOCATION_ID` | _(empty)_ | GHL location id. |
| `GHL_BASE_URL` | _(empty)_ | GHL API base. |
| `GHL_OUTBOUND_MODE` | `webhook` | `webhook` (live) or `mcp` (descriptor-only dry-run). |
| `GHL_DRY_RUN` | `true` | When true, configured webhook sends stay dry-run (no network). |
| `WEBHOOK_DEBOUNCE_ENABLED` | `false` | Coalesce inbound bursts (see `docs/universal-webhook.md`). |
| `WEBHOOK_DEBOUNCE_MS` | `2500` | Debounce window in ms. |

`ghl_configured` = base_url + api_key + location_id all set. `ghl_send_enabled` =
configured AND not dry_run.

## Migration

`agent-studio/migrations/0007_ghl_provider.sql` widens the
`integration_connections.provider` CHECK constraint to include `'ghl'` (idempotent:
drops + re-adds the constraint). Run automatically by the memoized migration runner at
startup (non-fatal on DB-not-ready).