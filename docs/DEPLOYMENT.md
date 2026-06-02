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

Default ports:

- Console: `3000`
- Agent Studio: `8010`

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
- persistent Sagad database and pgvector.
- secret management.
- auth and role-based access.
- durable audit storage.
- backup and restore procedures.
- image publishing and deploy automation.
