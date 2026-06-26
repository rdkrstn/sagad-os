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

## 7. Dormant auto-send — the guardrail never emitted "pass"

**Symptom:** Auto-send was dead code. Every conversation landed in `needs_approval` /
`not_sent`, even obvious low-risk pricing replies. The "auto-send gate" documented in
`docs/adapters/ghl.md` never fired.

**Root cause:** `_maybe_auto_send_universal` requires `compliance_status == "pass"` to send.
But the guardrail (`graph.run_guardrail`) only ever emits `needs_review` or `blocked` —
**never `pass`**. So the `pass` branch was unreachable and auto-send was dormant by
construction. The original Phase-4 plan said to leave `_maybe_auto_send_universal`
unchanged and just "produce a pass verdict" upstream — but producing `pass` alone was not
sufficient, because the send gate also had a **second, independent confidence check
hardcoded at `confidence >= 0.88`**. In the dev-e2e container the dry-run classifier
produced `confidence ≈ 0.48` (fresh knowledge store), so even after promotion the send gate
blocked. Two gates, two thresholds, silently disagreeing.

**Fix:** A RevOps "safe lane" (`agent_studio/revops_autosend.py`,
`revops_autosend_decision`) promotes a narrow allowlist of low-risk intents from
`needs_review` → `pass` **after** `graph.ainvoke`, only when the guardrail did not block.
Crucially, the promotion threshold and the send-gate threshold now share **one** knob:
`REVOPS_AUTOSEND_CONFIDENCE`. `_maybe_auto_send_universal` was changed from
`confidence >= 0.88` to `confidence >= float(settings.revops_autosend_confidence)` so a
promoted conversation always clears the send gate. `blocked` always wins (the safe lane is
skipped when the guardrail blocked). Empty allowlist default → no promotion → prior
behavior unchanged. I deviated from the plan's "leave it unchanged" instruction because the
plan's assumption was wrong — producing `pass` is not enough when a second hardcoded gate
exists. Verified: `tests/test_revops_autosend.py` + the `dev_e2e.py` tiered check
(intent=`pricing_lead`, risk=`low`, compliance=`pass`, approval=`sent`, send=`dry_run`).

**Lesson:** A guard that depends on a value an upstream component never produces is dead
code, not a safety feature. And when two gates guard the same action, they must share one
threshold or they silently disagree — the failure mode is "looks promoted but still
doesn't send," which is invisible without an end-to-end check. The dev-e2e roundtrip is
what caught it; unit tests with a mocked graph at `confidence=0.90` did not.

## 8. GHL inbound poller — "private integration directly to GHL inbound" conflated auth with delivery

**Symptom / misconception:** The theory was "skip the webhook, go straight to GHL inbound
via the Private Integration Token." That conflates **auth** with **delivery**.

**Root cause:** A GHL Private Integration Token is a static bearer credential (read/send
scopes). It enables **polling** the Conversations API; it is **not** a push channel. The
un-throttled push channel is GHL's native `InboundMessage` webhook — a Marketplace/OAuth-app
feature signed with Ed25519 (`x-wh-signature`), **not** the HMAC we built, and subscription
is UI-only (no API). So "direct inbound, not via webhook" really means: build a poller now
(env-only creds, no Marketplace app), with the native webhook as a later flip of
`GHL_SIGNATURE_SCHEME=ed25519`.

**Fix:** `agent_studio/ghl_poller.py` polls `GET /conversations/search` + per-conversation
`GET /conversations/{id}/messages?lastMessageId=`, filters inbound, and feeds the **same**
`_run_universal_inbound` pipeline as `POST /webhooks/ghl` (no parallel graph path).
Watermarks live in `integration_sync_state` (`payload["last_message_ids"]` per-conversation
cursor) and advance only after a successful persist. A `ghl-api-architect` sub-agent
confirmed the exact endpoint shapes first — and surfaced a non-obvious gotcha: the Search
response does **not** reliably expose `lastMessageDate`/`lastMessageId`, so the per-conv
`lastMessageId` cursor (not a timestamp) is the real watermark, and the Get-Messages
response wraps the array under `messages.messages` (documented bug #54). Both are handled.
No-creds / DB-not-ready skip; 429 honors `Retry-After`-or-exponential backoff (capped 60s).
The Ed25519 verifier (`Ed25519GhlVerifier`) is implemented now but inactive until
`GHL_SIGNATURE_SCHEME=ed25519`.

**Lesson:** When a user's mental model of an integration is off, name the confusion
explicitly (auth ≠ delivery) and build the thing that actually exists (a poller), while
laying groundwork for the thing that doesn't yet (the native webhook) behind a config flag.
And verify third-party endpoint shapes with a specialist sub-agent before coding — the
response-shape gotchas would have caused silent zero-ingest bugs.

## Guardrails going forward (enforced by CI + the loop-engineering skill)

1. **E2E is the definition of done:** `docker compose ps` shows `sagad-agent-studio
   (healthy)` AND `scripts/dev-e2e.sh` is `ALL GREEN` AND `uv run python -m pytest` passes.
   If any is red, do not write docs — report what broke.
2. **No new LLM dependency for CI:** `LLM_MODE=dry_run` + deterministic embeddings.
3. **Preserve existing behavior:** opt-in env flags for contract-changing features.
4. **Don't fabricate:** honest stubs + tests + doc notes over fake execution.
5. **Fast-fail diagnostics:** CI dumps the health-check log + service logs on failure.