# CI and Dev E2E

The CI pipeline gates PRs on a real end-to-end roundtrip, not just unit tests. The same
script runs locally, so "works on my machine" == "works in CI."

## Jobs (`.github/workflows/ci.yml`)

| Job | Needs | What it proves |
|---|---|---|
| `lint-and-test` | — | gitleaks + Trivy fs scan; v1 `npm ci`, audit, lint, `tsc --noEmit`, `npm run build`. |
| `containers` | `lint-and-test` | Builds both runtime images, Trivy-scans each. |
| `backend-tests` | `lint-and-test` | Installs poppler + tesseract, `uv sync --frozen`, `uv run python -m pytest` with `DATABASE_URL="" LLM_MODE=dry_run` (credential-free, no GPU). |
| `compose-smoke` | `containers` | Boots `compose.vps.example.yaml`, polls `/health/ready` with fast-fail diagnostics, curls `/health` + `/health/live` + `/health/ready`, verifies console→Agent-Studio connectivity. |
| `dev-e2e` | `backend-tests` | Boots compose with `LLM_MODE=dry_run` and runs `scripts/dev-e2e.sh` — the full live roundtrip: Chatwoot + GHL webhooks, conversation fetch + persistence + traces, draft SSE stream, agents CRUD, knowledge search. **Must be `ALL GREEN`.** |

### compose-smoke fast-fail diagnostics
Before the health curls, the job polls `/health/ready` and prints
`docker inspect sagad-agent-studio --format 'health={{.State.Health.Status}}'`. On any
non-zero exit, the cleanup trap dumps `compose ps --format json`, the full health-check
log (`json .State.Health.Log`), and the last 120 log lines of `sagad-db`/`agent-studio`/
`sagad-console` — so an unhealthy container says *why* instead of just "connection refused."
`docker network create client_internal_network` is idempotent (`|| true`).

## Local: `scripts/dev-e2e.sh`

One command — boots compose, runs the roundtrip, tears down:

```bash
bash scripts/dev-e2e.sh            # boot + run + down
bash scripts/dev-e2e.sh --no-down  # leave the stack up for re-probing
```

The script sets credential-free defaults (`LLM_MODE=dry_run`, deterministic embeddings,
`CHATWOOT_WEBHOOK_TOKEN`) and traps EXIT so teardown + diagnostics always run. Override any
of the documented env vars (e.g. `AUTH_SECRET`, `SAGAD_INTEGRATION_ENCRYPTION_KEY`) for your
environment.

### Quick re-probe against an already-running stack
If the stack is already up (e.g. your VPS or a local `docker compose up -d`), skip the boot
and run the probe directly — pull secrets from the container without echoing them:

```bash
INTERNAL_SECRET=$(docker exec sagad-agent-studio printenv AGENT_STUDIO_INTERNAL_SECRET | tr -d '\r\n') \
CHATWOOT_WEBHOOK_TOKEN=$(docker exec sagad-agent-studio printenv CHATWOOT_WEBHOOK_TOKEN | tr -d '\r\n') \
BASE_URL=http://127.0.0.1:8010 \
uv run --project agent-studio python scripts/dev_e2e.py
```

Expected: `23/23 checks passed` → `ALL GREEN`, exit 0.

## Backend unit/TestClient tests

```bash
cd agent-studio
DATABASE_URL="" LLM_MODE=dry_run uv run python -m pytest -q
```

`DATABASE_URL=""` overrides any local `.env` so the in-memory store is used (no Postgres
needed). `LLM_MODE=dry_run` selects the deterministic stub model. The full suite
(including `test_universal_webhook.py`, `test_ghl_adapter.py`, `test_debounce.py`,
`test_draft_stream.py`, `test_agents_crud.py`, and the 14 Chatwoot tests in `test_app.py`)
must pass.

## Required PR checks (branch protection)

Require: `lint-and-test`, `containers`, `backend-tests`, `compose-smoke`, `dev-e2e`.
The PR template checklist points at `scripts/dev-e2e.sh` and these job names.

## Guardrails baked in
- **E2E is the definition of done** — `dev-e2e` must be `ALL GREEN` and the container
  `(healthy)`.
- **No new LLM dependency for CI** — `LLM_MODE=dry_run` + deterministic embeddings; no
  OpenAI key, no GPU.
- **Preserve existing behavior** — debouncing + universal webhook are opt-in via env, so
  the synchronous Chatwoot tests stay green.