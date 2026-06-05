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
- `litellm`: optional model gateway, enabled only with the `litellm` compose profile.

Default ports:

- Console: `3000`
- Agent Studio: `8010`
- Sagad Postgres/pgvector: `5433` on the host, `5432` inside compose.
- LiteLLM: `4000` when the optional `litellm` profile is enabled.

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

The first self-host preview uses the default Johnred Workspace organization. The access-control contract is:

- Owner and Admin users can edit integration setup.
- Supervisor users can monitor redacted integration status and use HITL approval flows, but cannot edit provider credentials.

Replace the preview membership flow with invites, organization management, and role review before production use.

## Integration Setup And Secrets

Keep Agent Studio as the only service that talks to provider APIs. The console must not expose Chatwoot, Twenty, LangSmith, MCP, or client-internal credentials to browser code.

Owners and Admins configure Chatwoot and Twenty CRM through the operator/admin Integrations page. Supervisors can view redacted health and readiness only. Agent Studio stores connection metadata in Sagad Postgres and stores provider tokens/API keys as encrypted secret versions when `DATABASE_URL` is configured.

Set a durable encryption key for deployments that save provider credentials:

```env
SAGAD_INTEGRATION_ENCRYPTION_KEY=replace-with-strong-integration-secret-key
```

The integration setup API returns redacted status only: configured flags, missing fields, dry-run state, write-gate state, health detail, and `has_*` booleans. It must not return raw API tokens, webhook tokens, or API keys.

## Realtime Sync

The Sagad Console can refresh queue and review screens from Agent Studio WebSocket events. Configure both services with the same realtime secret:

```env
SAGAD_WS_PUBLIC_URL=wss://sagad-agent.example.com/ws/conversations
SAGAD_REALTIME_SECRET=replace-with-realtime-secret
```

`SAGAD_WS_PUBLIC_URL` is browser-facing and belongs in the console environment. `SAGAD_REALTIME_SECRET` is shared by the console and Agent Studio so the console can mint short-lived WebSocket tokens from the Auth.js session.

In Nginx Proxy Manager, enable WebSocket support on the proxy host that forwards to `sagad-agent-studio:8010`. Without WebSocket upgrade support, the console will show live sync as disabled or reconnecting.

## Health Checks

After local preview deployment:

```powershell
Invoke-WebRequest -UseBasicParsing http://127.0.0.1:8010/health
Invoke-WebRequest -UseBasicParsing http://127.0.0.1:8010/health/live
Invoke-WebRequest -UseBasicParsing http://127.0.0.1:8010/health/ready
Invoke-WebRequest -UseBasicParsing http://127.0.0.1:8010/integrations
Invoke-WebRequest -UseBasicParsing http://127.0.0.1:8010/integrations/twenty/health
Invoke-WebRequest -UseBasicParsing http://127.0.0.1:8010/integrations/litellm/health
Invoke-WebRequest -UseBasicParsing http://127.0.0.1:8010/integration-configs
Invoke-WebRequest -UseBasicParsing http://127.0.0.1:8010/diagnostics/events
```

After VPS deployment with the local `compose.vps.yaml`, check from inside the Docker network:

```bash
docker exec sagad-agent-studio python -c "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:8010/health').read().decode())"
docker exec sagad-agent-studio python -c "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:8010/health/ready').read().decode())"
docker exec sagad-console node -e "fetch('http://sagad-agent-studio:8010/health').then(r=>r.text()).then(console.log)"
```

Docker healthchecks use `/health/live` so the container stays alive while provider setup is incomplete. Use `/health/ready` to diagnose database migration or seed failures; it returns a non-200 response when database readiness fails. If `sagad-agent-studio` is unhealthy on the VPS, run:

```bash
docker inspect --format='{{json .State.Health}}' sagad-agent-studio | python -m json.tool
docker logs --tail=200 sagad-agent-studio
docker exec sagad-agent-studio python -c "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:8010/health/ready').read().decode())"
```

For provider failures where Agent Studio returns HTTP 200 but the external action fails, use the console first:

- `Conversation Review -> Tool & Delivery Results` shows the Chatwoot/Twenty action status, HTTP status, error type, and clipped provider response body for the selected conversation.
- `Integrations -> Backend Diagnostics` shows recent Agent Studio webhook/send events, including rejected webhook tokens, ignored outgoing/private events, duplicate retries, send attempts, and failed provider responses.

The server-side diagnostics endpoint is:

```bash
docker exec sagad-console node -e "fetch('http://sagad-agent-studio:8010/diagnostics/events', {headers:{'X-Sagad-Internal-Secret':process.env.AGENT_STUDIO_INTERNAL_SECRET || ''}}).then(r=>r.text()).then(console.log)"
```

Use `docker logs` only when the diagnostics endpoint, health endpoint, or console route cannot be reached.

## CI-Gated VPS Deploy

Before deploying a branch or tag to the VPS, make sure GitHub Actions has passed:

- Security Scan;
- Frontend;
- Agent Studio;
- Container Builds;
- Docker Compose Smoke;
- Release Check for version tags.

Deploy manually until the release flow is stable:

```bash
cd ~/apps/sagad-os
git fetch origin
git checkout main
git pull --ff-only origin main
docker compose -f compose.vps.yaml config --quiet
docker compose -f compose.vps.yaml up -d --build
docker compose -f compose.vps.yaml ps
```

Then verify:

```bash
docker exec sagad-agent-studio python -c "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:8010/health/live').read().decode())"
docker exec sagad-agent-studio python -c "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:8010/health/ready').read().decode())"
docker exec sagad-console node -e "fetch('http://sagad-agent-studio:8010/health/live').then(r=>r.text()).then(console.log)"
```

Rollback is also manual:

```bash
git log --oneline -5
git checkout <previous-good-sha-or-tag>
docker compose -f compose.vps.yaml up -d --build
```

For schema-changing releases, take a database backup before deploy. Git rollback does not automatically reverse database migrations.

## Optional LiteLLM Gateway

LiteLLM is optional. It lets Agent Studio use one OpenAI-compatible gateway for OpenAI and DeepSeek test credits.

Local preview:

```powershell
docker compose -f compose.preview.yaml --profile litellm up -d --build
```

VPS preview:

```bash
docker compose -f compose.vps.yaml --profile litellm up -d --build
```

Set these values in the real ignored `.env` file:

```env
LITELLM_ENABLED=true
LITELLM_BASE_URL=http://sagad-litellm:4000/v1
LITELLM_MASTER_KEY=replace-with-strong-litellm-key
OPENAI_API_KEY=replace-with-openai-key
DEEPSEEK_API_KEY=replace-with-deepseek-key
```

Then point Agent Studio model calls at the gateway:

```env
OPENAI_BASE_URL=http://sagad-litellm:4000/v1
```

Do not expose LiteLLM publicly unless you add authentication, rate limits, and a clear operational reason.

## Optional Sentry Monitoring

Sentry is optional runtime crash monitoring. It should not be required for local contributors or self-host smoke tests.

Use Sentry for frontend/backend exceptions. Use LangSmith for graph and agent traces. Use Uptime Kuma for uptime. Use Sagad Diagnostics for provider/webhook/tool failures.

Example env:

```env
SENTRY_DSN=
SENTRY_ENVIRONMENT=preview
SENTRY_RELEASE=
SENTRY_TRACES_SAMPLE_RATE=0.1
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

Keep local maintainer files local and ignored. Real per-server `.env`, `compose.vps.yaml`, maintainer memory/status/task notes, Obsidian state, screenshots, generated caches, key files, and certificates should not be committed.

## Production Notes

Before production use, add:

- TLS and reverse proxy config.
- hardened Postgres/pgvector operations, migrations, and backups.
- secret management, key rotation, and encrypted tenant/client credentials.
- auth runbooks, role review, and session hardening.
- durable audit retention and export policy.
- backup and restore procedures.
- image publishing and deploy automation.
