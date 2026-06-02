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

## VPS Compose With Nginx Proxy Manager

Use `compose.vps.example.yaml` as a template when the VPS already has Nginx Proxy Manager and a shared external Docker network named `client_internal_network`.

Preflight:

```bash
docker network inspect client_internal_network >/dev/null
```

If the network does not exist yet:

```bash
docker network create client_internal_network
```

Copy the example env and compose files to local ignored files:

```bash
cp .env.example .env
cp compose.vps.example.yaml compose.vps.yaml
```

Edit `.env` with real VPS values and secrets. Edit `compose.vps.yaml` only when that VPS uses different container names, networks, ports, or proxy assumptions. Do not commit either local file.

Start the stack:

```bash
docker compose -f compose.vps.yaml config --quiet
docker compose -f compose.vps.yaml up -d --build
docker compose -f compose.vps.yaml ps
```

Nginx Proxy Manager should route the Sagad Console proxy host to:

```text
Forward Hostname / IP: sagad-console
Forward Port: 3000
```

Do not publish Agent Studio publicly unless you intentionally add a protected route for webhooks. If Chatwoot runs on the same `client_internal_network`, configure its webhook URL as:

```text
http://sagad-agent-studio:8010/webhooks/chatwoot
```

## Health Checks

After local preview deployment:

```powershell
Invoke-WebRequest -UseBasicParsing http://127.0.0.1:8010/health
Invoke-WebRequest -UseBasicParsing http://127.0.0.1:8010/integrations
Invoke-WebRequest -UseBasicParsing http://127.0.0.1:8010/integrations/twenty/health
```

After VPS deployment with the local `compose.vps.yaml`, check from inside the Docker network:

```bash
docker exec sagad-agent-studio python -c "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:8010/health').read().decode())"
docker exec sagad-console node -e "fetch('http://sagad-agent-studio:8010/health').then(r=>r.text()).then(console.log)"
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
