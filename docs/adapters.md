# Adapters

Adapters let Sagad OS connect to external tools without becoming those tools.

## Reference Adapters

| Adapter | Purpose | v0.1 state |
|---|---|---|
| Chatwoot | Channel intake and approved replies | Reference adapter |
| Twenty CRM | Customer and lead context | Reference adapter |
| Markdown Knowledge Pack | Approved answer source | Local seed |
| Generic Webhooks | Future connector primitive | Planned |
| MCP/FastMCP | Future tool facade behind Agent Studio | Planned |

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
