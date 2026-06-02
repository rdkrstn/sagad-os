# Deployment

Sagad OS supports self-hosted and managed deployment models. The first deploy target is a single VPS preview.

## Preview Compose

Use `compose.preview.yaml` for local or VPS smoke testing.

```powershell
docker compose -f compose.preview.yaml build
docker compose -f compose.preview.yaml up -d
```

Services:

- `sagad-console`: Next.js supervisor console.
- `agent-studio`: FastAPI + LangGraph backend preview.
- `sagad-db`: Postgres 16 with pgvector for Sagad-owned data.

Default ports:

- Console: `3000`
- Agent Studio: `8010`
- Sagad Postgres/pgvector: `5433` on the host, `5432` inside compose.

## Health Checks

After deployment:

```powershell
Invoke-WebRequest -UseBasicParsing http://127.0.0.1:8010/health
Invoke-WebRequest -UseBasicParsing http://127.0.0.1:8010/integrations
Invoke-WebRequest -UseBasicParsing http://127.0.0.1:8010/integrations/twenty/health
```

## VPS Layout

For the first working preview, Sagad OS can run beside Chatwoot, Twenty CRM, and Uptime Kuma on the same VPS.

```text
GCE VPS
|-- Chatwoot
|-- Twenty CRM
|-- Uptime Kuma
|-- Sagad Console
`-- Agent Studio
```

Keep Agent Studio as the only service that talks to provider APIs, databases, vector stores, MCP servers, or client internal systems.

## Production Notes

Before production use, add:

- TLS and reverse proxy config.
- hardened Postgres/pgvector operations, migrations, and backups.
- secret management and encrypted tenant/client credentials.
- auth runbooks, role review, and session hardening.
- durable audit retention and export policy.
- backup and restore procedures.
- image publishing and deploy automation.
