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

## Console Auth

The Sagad Console is protected by Auth.js. Browser users without a session are redirected to `/api/auth/signin`.

Email magic-link login requires these environment variables:

```env
AUTH_URL=https://sagad.example.com
AUTH_SECRET=replace-with-auth-secret
EMAIL_SERVER=smtp://user:password@smtp.example.com:587
EMAIL_FROM=Sagad OS <noreply@example.com>
```

Google OAuth is optional. Set both variables to show the Google sign-in option:

```env
AUTH_GOOGLE_ID=google-oauth-client-id
AUTH_GOOGLE_SECRET=google-oauth-client-secret
```

Configure the Google OAuth client with these redirect URIs:

- Local: `http://localhost:3000/api/auth/callback/google`
- Production: `https://sagad.example.com/api/auth/callback/google`

The production JavaScript origin should match `AUTH_URL`, for example `https://sagad.example.com`.

The first self-host preview assigns signed-in users to the default Home Services Demo organization as supervisors. Replace this with invites and organization management before production use.

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
