---
name: loop-engineering
description: Token/GPU-efficient engineering loop for sagad-os. Use when implementing or fixing a feature in this repo — scope with targeted grep/read, batch edits, verify with the e2e roundtrip + pytest + docker health, loop until green, and only declare done when the stack is healthy and e2e is green. Enforces the "not complete unless everything works" guardrail.
---

# Loop Engineering (sagad-os)

This skill is the reusable form of the workflow that drove the universal-webhook +
Docker-health + dev-e2e work. The harness runs on Ollama + glm-5.2, so every token is
GPU time — the loop is built to minimize re-reading, re-building, and re-deriving.

## Hard guardrails (non-negotiable)

1. **E2E is the definition of done.** Nothing is "complete" unless ALL of:
   - `docker compose ps` shows `sagad-agent-studio (healthy)`,
   - `scripts/dev-e2e.sh` (or `scripts/dev_e2e.py` against a booted stack) is **ALL GREEN**,
   - `cd agent-studio && uv run python -m pytest` passes.
   If any is red, do **not** write or update technical docs — instead report what broke
   and the failing evidence (the postmortem is the only doc written from a red state).
2. **Correct yourself if you have to.** A failing verify is a signal to fix, not to
   narrate around. Loop: read-failure → targeted-fix → re-verify.
3. **Don't fabricate working surface.** If a planned executor/subsystem would require a
   new dependency or untested runtime, ship an honest, clearly-labeled stub + a test for
   the stub behavior + a doc note explaining why, rather than fake execution. "Honest
   dry-run" beats "pretend it ran."
4. **No new LLM dependency for CI/e2e.** The booted roundtrip uses `LLM_MODE=dry_run`
   (deterministic stub model) + deterministic embeddings (auto when `OPENAI_API_KEY`
   unset). CI must never require an OpenAI key or a GPU.
5. **Preserve existing behavior.** New, optional behavior (debouncing, universal
   webhook) is opt-in via env so existing synchronous tests stay green unchanged.

## The loop

### 1. Scope (cheap, targeted — never re-read whole files)
- Start with `Grep` (pattern + `output_mode: content` + `-n`) and `Glob`, not `Read`.
- Cite `file:line` for every claim. Read only the specific line ranges you need.
- Re-derive nothing already established in the conversation or git history.

### 2. Implement (batched)
- Batch independent edits in a single message (multiple `Edit`/`Write` calls at once).
- Match surrounding code: comment density, naming, idiom. No drive-by refactors.
- Reuse existing helpers (`_sagad_conversation_id`, `_record_diagnostic_event`,
  `graph.ainvoke`, the reranker, `conftest.py` fixtures) — do not duplicate.

### 3. Verify (scoped, fast)
- Unit/TestClient layer first: `cd agent-studio && DATABASE_URL="" LLM_MODE=dry_run uv run python -m pytest -q`.
- Live roundtrip: `bash scripts/dev-e2e.sh` (boots compose, runs `scripts/dev_e2e.py`,
  tears down). For a quick re-probe against an already-running stack, run
  `scripts/dev_e2e.py` directly with `INTERNAL_SECRET` + `CHATWOOT_WEBHOOK_TOKEN` pulled
  from `docker exec sagad-agent-studio printenv …` (never echo secret values; scrub temp files).
- Scope docker rebuilds to the changed service: `docker compose build sagad-agent-studio`
  (not a full rebuild) unless the change is cross-service.

### 4. Loop until green (bounded)
- On a failing verify: read the actual error line, form the minimal fix, re-verify.
- Cap at ~N iterations per failure; if you cannot get green, surface a blocker with the
  failing evidence instead of looping forever or declaring done.
- Stop early on green — do not pad with extra "verification."

### 5. Done gate (hard)
Only declare done when the three guardrail-1 conditions hold. State outcomes plainly:
which checks passed, with the real output. If something was skipped or stubbed, say so.

## Common fixes already in the repo (read before re-deriving)
- **Docker unhealthy** → lifespan migration failure. Already fixed via
  `initialize_database_safe` + memoized `database_ready` + `/health/ready`. Don't re-run
  migrations on every health probe.
- **Live Chatwoot 500** → `embeddings.embed_text` raised on a bad/unreachable OpenAI key.
  Already fixed: it falls back to the dimension-aligned deterministic embedding on any
  exception. The pipeline never 500s without a valid OpenAI key; semantic recall is
  degraded until `OPENAI_API_KEY` is set.
- **`dev_e2e.py` false reds** → `/knowledge/search-test` is POST (not GET); agent ids are
  normalized `[^a-z0-9_]→_`, so use underscore ids in CRUD tests. Already fixed.
- **v1 build `Module not found: ./icons/*.mjs`** → corrupted partial `lucide-react`
  install; `rm -rf node_modules/lucide-react && npm install`. **`Cannot find type
  definition for 'nodemailer'`** → pin `@types/nodemailer@^7.0.12` (8.x stub ships no
  `index.d.ts`). Already fixed.

## Spawn sub-agents for independent tracks
When tracks are independent (e.g., GHL adapter vs CI workflow vs tests vs docs), spawn
parallel `Agent` calls in one message. Verification is always run by this loop, never
delegated — the main loop is the source of truth for "green."