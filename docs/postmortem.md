# Postmortem — Universal Webhook + Docker-Health + Dev E2E effort

What went wrong, what broke during implementation, and how each was fixed. Written from a
verified-green state (`scripts/dev-e2e.sh` → `ALL GREEN`, `sagad-agent-studio (healthy)`,
full `pytest` suite passing) — per the project guardrail that docs come only after
everything works, and that the postmortem records the breakage honestly.

## 1. Docker "unhealthy" — lifespan migration failure killed uvicorn

**Symptom:** `sagad-agent-studio` went `(unhealthy)` on boot. The compose healthcheck
targets `/health/live`, which only fails when uvicorn never serves.

**Root cause:** The FastAPI `lifespan` startup called `initialize_database(get_settings())`
which runs **all** migrations. A DB-not-ready or migration error raised, uvicorn never
started serving, `/health/live` stayed connection-refused → 10 retries × 10s after the
`start_period` → unhealthy. The healthcheck proved liveness, but the failure was in
readiness/startup, so "unhealthy" was a delayed symptom of a startup crash.

**Fix (Track A):**
- `initialize_database_safe` wraps migration init in try/except inside `lifespan`, logs a
  `startup.database_init_failed` diagnostic, sets `_db_ready = False`, and **does not
  re-raise**. uvicorn keeps serving → `/health/live` stays 200 (container healthy) while
  `/health/ready` reports not-ready. One change stops migration errors from killing the
  container.
- `/health/ready` is memoized + cheap (`SELECT 1` ping) instead of re-running all
  migrations on every 10s probe.
- Compose healthcheck tuned: `start_period: 40s`, `retries: 15`, target `/health/live`
  (readiness is asserted by CI curls, not the liveness probe).
- CI `compose-smoke` now polls `/health/ready` and dumps the health-check log + service
  logs on any failure, so an unhealthy container says *why*.

**Lesson:** Liveness and readiness are different concerns. A migration error is a
readiness failure; making it crash liveness turned a recoverable condition into a
container-restart loop.

## 2. Live Chatwoot webhook 500 — OpenAI embedding call crashed the request

**Symptom:** `POST /webhooks/chatwoot` returned 500 live, even though the TestClient tests
passed.

**Root cause:** `store.list_memory_items` → `embedding_service.embed_text` → real OpenAI
HTTP call. The container had an invalid/unreachable `OPENAI_API_KEY`, so the call raised
`RuntimeError`, which propagated up and 500'd the webhook. The unit suite never caught this
because `conftest.py` stubs `embed_text`.

**Fix:** `embeddings.embed_text` now catches **any** exception from the OpenAI path and
falls back to the dimension-aligned `deterministic_embedding` (hash-based, correct
dimensionality) with a warning, instead of raising. The pipeline (memory + retrieval) now
succeeds without a live OpenAI key; semantic recall is degraded until a valid
`OPENAI_API_KEY` is set, but nothing 500s.

**Lesson:** External-dependency failures in a hot request path must degrade, not crash.
Unit tests with stubbed deps don't prove live behavior — the dev-e2e roundtrip does.

## 3. v1 frontend build — corrupted `lucide-react` + broken `@types/nodemailer` stub

**Symptom:** `npm run build` failed with hundreds of
`Module not found: Can't resolve './icons/*.mjs'` inside `lucide-react`, then
`Cannot find type definition file for 'nodemailer'`.

**Root cause (a):** `node_modules/lucide-react` had only 283 of ~1962 icon files — a
corrupted/partial extraction. The barrel referenced icons (e.g. `a-arrow-down.mjs`) that
weren't on disk. **Root cause (b):** `@types/nodemailer@8.0.0` declared `types=index.d.ts`
but shipped no `index.d.ts` (a broken stub), and `nodemailer@9` bundles no types of its own.

**Fix:** (a) `rm -rf node_modules/lucide-react && npm install` restored all 1962 icons
(local corruption; a fresh CI install is fine). (b) Pinned `@types/nodemailer` to
`^7.0.12` (last complete release). `npm run build` now exits 0 (0 module-not-found, 0 type
errors).

**Lesson:** "Module not found" on a popular library is often a corrupted local install, not
a real dependency error — verify file counts before chasing import graphs. And a
`@types/*` package that declares a types entry but doesn't ship it is a broken stub; pin to
the last known-good version.

## 4. `dev_e2e.py` false reds — wrong verb + id-normalization mismatch

**Symptom:** `scripts/dev_e2e.py` reported failures against a stack that was actually
working.

**Root cause (a):** `/knowledge/search-test` is a `POST` taking a
`KnowledgeSearchTestRequest` body and returning `{"hits": [...]}`, but the script used
`GET` with query params → 405. **Root cause (b):** the agents CRUD test used a hyphenated
id `e2e-test-<hex>`, but `save_agent` normalizes `[^a-z0-9_]→_`, so the stored/listed id was
`e2e_test_<hex>` and the `created agent listed` membership check failed. (The same
mismatch made `DELETE /agents/{hyphen-id}` 404 until `delete_agent` was fixed to apply the
same normalization.)

**Fix:** (a) switched to `POST` with the JSON body, reading `.get("hits")`. (b) use an
already-normalized underscore id so POST/GET/DELETE agree. Also fixed `agents.delete_agent`
to normalize the id the same way `save_agent` does. Verified: `23/23 checks passed`, `ALL GREEN`.

**Lesson:** A test harness that reports red on a working system is worse than no harness —
it erodes trust in the green signal. The e2e script is itself a code artifact that needs
the same verify-loop as the feature.

## 5. Debounce breaking synchronous tests → made opt-in

**Risk:** A debounce layer that returns `202` and processes in the background would change
the webhook response contract from synchronous `ConversationRecord` to async, breaking the
14 Chatwoot tests in `test_app.py` that assert on the synchronous response.

**Fix:** `WEBHOOK_DEBOUNCE_ENABLED` defaults to **false**. Debouncing only changes behavior
for the universal/GHL handler when explicitly enabled; the Chatwoot dedicated route and all
sync tests are untouched. When enabled, the handler returns `202 debounced` with
`conversation_id` + `pending_keys`; results are observable via `GET /conversations/{id}`
and `/diagnostics/events`.

**Lesson:** New behavior that changes an existing contract must be opt-in, behind an env
flag, so the existing test net stays green and the change is reversible.

## 6. GHL MCP outbound — descriptor-only, not faked

**Temptation:** The plan called for an MCP outbound executor. It would have been easy to
return `status=sent` from a fake executor.

**Correct call:** The Agent Studio MCP gateway (`mcp_gateway.py`) is descriptor-only by
design — it builds redacted tool descriptors and has no execution runtime or credential
surface. A real executor needs an MCP-client dependency + server config + approval-gated
invocation: untested surface area. So `mcp` mode returns an **honest dry-run** that names
the descriptor it *would* invoke (`mcp://ghl.messages.send?conversationId=…`), with a test
asserting that behavior, and this doc note. Live sends use `GHL_OUTBOUND_MODE=webhook`.

**Lesson:** "Correct yourself if you have to" includes refusing to fabricate working
surface. An honest dry-run with a clear doc note beats a fake success that lies about
having sent something.

## Guardrails going forward (enforced by CI + the loop-engineering skill)

1. **E2E is the definition of done:** `docker compose ps` shows `sagad-agent-studio
   (healthy)` AND `scripts/dev-e2e.sh` is `ALL GREEN` AND `uv run python -m pytest` passes.
   If any is red, do not write docs — report what broke.
2. **No new LLM dependency for CI:** `LLM_MODE=dry_run` + deterministic embeddings.
3. **Preserve existing behavior:** opt-in env flags for contract-changing features.
4. **Don't fabricate:** honest stubs + tests + doc notes over fake execution.
5. **Fast-fail diagnostics:** CI dumps the health-check log + service logs on failure.