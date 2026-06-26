# Adapters

Adapters let Sagad OS connect to external tools without becoming those tools.

## Reference Adapters

| Adapter | Purpose | v0.1 state |
|---|---|---|
| Chatwoot | Channel intake and approved replies | Reference adapter (`POST /webhooks/chatwoot`) |
| Twenty CRM | Customer and lead context | Reference adapter |
| GoHighLevel (GHL) | Channel intake + approved replies via universal webhook | Working (`POST /webhooks/ghl`) — see [`adapters/ghl.md`](./adapters/ghl.md) |
| Markdown Knowledge Pack | Approved answer source | Local seed |
| Universal Webhook (`ChannelAdapter` registry) | Provider-pluggable inbound/outbound behind one route | Working (`POST /webhooks/{provider}`) — see [`universal-webhook.md`](./universal-webhook.md) |
| MCP/FastMCP | Tool facade behind Agent Studio | Descriptor-only by design (no executor runtime); GHL `mcp` outbound is an honest dry-run |

## Rules

- Store provider credentials server-side only.
- Return redacted status to the Console.
- Route privileged calls through Agent Studio.
- Keep writes disabled or dry-run until supervisor approval gates pass.
- Log every tool plan and result in Sagad Audit.

## Adding A New Adapter

Start with a read-only health check, then add one read method, then one supervised write method. Do not expose browser-direct provider calls.

## Testing Adapters
Reference adapters are unit and integration tested under `tests/test_adapters.py`:
- **Chatwoot (`chatwoot.py`)**: Tests cover webhook payload parsing, unread counts, priority labels, conversation detail fetching, approved outgoing replies sending, and conversation status toggling.
- **Twenty CRM (`twenty.py`)**: Tests cover status resolution (disabled vs ready vs dry_run), people edge contact lookups (with masked email/phone PII output), and mutations (notes, tasks, lead stages).
