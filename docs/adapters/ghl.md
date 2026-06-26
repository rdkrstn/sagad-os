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

## Auto-send gate (RevOps tiered "safe lane")

The draft auto-sends only when `compliance_status == "pass"`. The guardrail
(`graph.run_guardrail`) only ever emits `needs_review` or `blocked` — never `pass` — so
historically **every** conversation landed in `needs_approval` and auto-send was dormant
dead code. The RevOps safe lane (`agent_studio/revops_autosend.py`,
`revops_autosend_decision`) promotes a narrow allowlist of low-risk intents from
`needs_review` → `pass` so the reply can auto-send without a supervisor round-trip.

Promotion happens in `_run_universal_inbound` **after** `graph.ainvoke`, **only** when the
guardrail did NOT block:

- `REVOPS_AUTOSEND_ENABLED=true` (kill-switch; default `true`),
- `intent ∈ REVOPS_AUTOSEND_INTENTS` (comma-list; **default empty → no promotion → prior
  behavior unchanged**),
- `risk_level == "low"`,
- `confidence >= REVOPS_AUTOSEND_CONFIDENCE` (default `0.88`), and
- the draft is non-empty.

**`blocked` always wins** — the safe lane is never consulted when the guardrail blocked.
The two confidence gates (safe-lane promotion + `_maybe_auto_send_universal`) share one
threshold (`REVOPS_AUTOSEND_CONFIDENCE`), so a promoted conversation always clears the
send gate. Start conservative (e.g. `pricing_lead,business_hours,status_check`); the
worst case is over-queued, never over-sent. See `docs/agents.md` and the postmortem
"dormant auto-send" entry.

## Read-only CRM context

When GHL is configured, `GhlAdapter.fetch_crm_context` pulls the contact + first
opportunity into graph state as `CrmContactContext` (`initial_state["crm_context"]`), so
the RevOps queue and the graph can reason about deal stage/value. It is **strictly
read-only** — no CRM writes, no write manifests.

- Endpoints: `GET /contacts/{contactId}` + `POST /opportunities/search` (body
  `{location_id, contact_id}`). Same Bearer + `Version: 2021-04-15` headers as sends.
- `contactId` comes from `raw_payload.contact.id`.
- **Never blocks inbound**: wrapped in an 8s `asyncio.wait_for` + a broad `except` →
  returns `None` on any timeout/HTTP/parse failure (the graph proceeds without CRM
  context). A 5-minute per-`contact_id` TTL cache avoids refetching on a hot thread.
- PII is masked (`_mask_secret`) — phone/email render as `+1***23` in the context, never
  raw. `CrmContactContext` carries `deal_stage` (opportunity `pipelineStage.name` or
  `status`) and `deal_value` (`monetaryValue`).

## Inbound poller (Private Integration Token)

A GHL Private Integration Token (read/send scopes) lets us **poll** the Conversations API;
it is **not** a push channel. So "direct inbound, not via webhook" means run a poller now
(env-only creds, no Marketplace app) and treat GHL's native `InboundMessage` webhook as a
later flip of a config flag. Implementation: `agent_studio/agent_studio/ghl_poller.py`,
started from the app `lifespan` only when `GHL_POLL_ENABLED=true`. Tests:
`agent-studio/tests/test_ghl_poller.py` (stubbed httpx — no real GHL in CI).

**Reuse, don't duplicate:** the poller feeds the SAME `_run_universal_inbound` pipeline as
`POST /webhooks/ghl` — there is no parallel graph path. It reuses `GhlAdapter.normalize` /
`ignores`, `_message_already_recorded`, `_universal_conversation_id`, `store.*`, and
`evaluate_tool_policy` (transitively).

**Per cycle** (one shared `httpx.AsyncClient`, same Bearer + `Version: 2021-04-15` headers):

1. `GET /conversations/search?locationId=&lastMessageDirection=inbound&status=recents&sortBy=last_message_date&sort=desc&limit=`
   — enumerate recently-active inbound threads (candidate set only).
2. For each conversation, `GET /conversations/{id}/messages?lastMessageId={cursor}&limit=`
   — page forward via the `lastMessageId` cursor (response wraps the array under
   `messages.messages`; `messages.lastMessageId` + `messages.nextPage` drive pagination).
3. Filter `direction == "inbound"` (reuse `_OUTBOUND_DIRECTIONS`); build a payload in the
   native `InboundMessage` shape `GhlAdapter.normalize` reads; dedup via
   `_message_already_recorded` (emits `ghl.poller.duplicate_skipped`); then
   `await _run_universal_inbound(...)`.

**Watermarks** live in `integration_sync_state` (`migrations/0008_tickets_revops.sql`):
`payload["last_message_ids"]` maps `conversation_id → lastMessageId` cursor — this is the
source of truth (the Search-Conversations response does **not** reliably expose
`lastMessageDate`/`lastMessageId`). `updated_since` is stamped to the cycle time for
observability only. A conversation's cursor advances **only after** its new messages are
successfully persisted, so a mid-cycle crash re-fetches (and dedup-skips) rather than drops.

**Safety:** no creds → silent skip; DB not ready → skip + continue (the lifespan DB-retry
task recovers); `429` → honor `Retry-After` when present, else exponential backoff capped
at 60s (`ghl.poller.rate_limited`); hard caps on conversations-per-cycle and
message-pages-per-conversation. GHL is env-only / single-location today, so the poller
runs under a system `StoreContext` (the store resolves the default org). Per-org GHL via
`integration_connections` + OAuth is a later track.

> **CI reality:** the poller roundtrip is pytest-only (stubbed httpx — `MockTransport`
> works in-process, not across the HTTP boundary to the booted container). `dev_e2e.py`
> asserts only that a poller-enabled boot stays healthy (GHL unconfigured → per-cycle
> no-creds skip → no-op).

## Native InboundMessage webhook (roadmap, not yet active)

GHL's native push channel is the Marketplace/OAuth-app `InboundMessage` webhook, signed
with **Ed25519** over the raw body (`x-wh-signature`) — **not** the HMAC above.
Subscription is UI-only (no API). The verifier is already implemented
(`Ed25519GhlVerifier` in `ghl.py`) and activates only when `GHL_SIGNATURE_SCHEME=ed25519`;
HMAC stays the default. To flip to the native webhook later: create the Marketplace app,
subscribe the `InboundMessage` event, set `GHL_SIGNATURE_SCHEME=ed25519` +
`GHL_NATIVE_WEBHOOK_KEY` (the public key GHL shows), and point the webhook at
`POST /webhooks/ghl`. The poller can then be turned off (`GHL_POLL_ENABLED=false`).

## Configuration

| Env | Default | Purpose |
|---|---|---|
| `GHL_WEBHOOK_SECRET` | _(empty)_ | HMAC secret for inbound verification. Empty = no-op (dev). |
| `GHL_SIGNATURE_SCHEME` | `hmac` | `hmac` (Workflow webhook) or `ed25519` (native InboundMessage). |
| `GHL_NATIVE_WEBHOOK_KEY` | _(empty)_ | Ed25519 public key for native-webhook verification. |
| `GHL_API_KEY` | _(empty)_ | Bearer token (outbound sends + CRM/poll reads). |
| `GHL_LOCATION_ID` | _(empty)_ | GHL location id. |
| `GHL_BASE_URL` | _(empty)_ | GHL API base. |
| `GHL_OUTBOUND_MODE` | `webhook` | `webhook` (live) or `mcp` (descriptor-only dry-run). |
| `GHL_DRY_RUN` | `true` | When true, configured sends stay dry-run (no network). |
| `GHL_POLL_ENABLED` | `false` | Start the inbound poller from the lifespan. |
| `GHL_POLL_INTERVAL_SECONDS` | `30` | Seconds between poll cycles. |
| `GHL_POLL_CONVERSATION_LIMIT` | `50` | Max conversations fetched per cycle. |
| `GHL_POLL_MESSAGE_LIMIT` | `20` | Messages page size per conversation. |
| `GHL_POLL_TIMEOUT_SECONDS` | `20` | Per-request httpx timeout for the poller. |
| `REVOPS_AUTOSEND_ENABLED` | `true` | Kill-switch for the tiered auto-send safe lane. |
| `REVOPS_AUTOSEND_INTENTS` | _(empty)_ | Comma-list of low-risk intents allowed to auto-send. |
| `REVOPS_AUTOSEND_CONFIDENCE` | `0.88` | Confidence threshold shared by both auto-send gates. |
| `WEBHOOK_DEBOUNCE_ENABLED` | `false` | Coalesce inbound bursts (see `docs/universal-webhook.md`). |
| `WEBHOOK_DEBOUNCE_MS` | `2500` | Debounce window in ms. |

`ghl_configured` = base_url + api_key + location_id all set. `ghl_send_enabled` =
configured AND not dry_run.

## Manual approve-send (provider dispatch)

`POST /conversations/{id}/approve-send` dispatches by provider: a GHL-sourced record
(`provider_conversation_id` set, no Chatwoot context) routes through
`GhlAdapter.send_outbound` + the `ghl.messages.send_approved` tool policy
(`evaluate_tool_policy`); Chatwoot records keep the existing send path verbatim. The GHL
path skips the Chatwoot `can_reply` 409 check. Sends are audited via `store.record_approval`
(provider-agnostic: `sent` / `send_failed`).

## Migration

`agent-studio/migrations/0007_ghl_provider.sql` widens the
`integration_connections.provider` CHECK constraint to include `'ghl'` (idempotent:
drops + re-adds the constraint). `migrations/0008_tickets_revops.sql` adds the
`integration_sync_state` watermark table (per-`organization_id`+`provider`,
`updated_since` + `payload` JSONB for the per-conversation `lastMessageId` cursor map) and
the ticket columns on `conversations`. Both run automatically by the memoized migration
runner at startup (non-fatal on DB-not-ready).