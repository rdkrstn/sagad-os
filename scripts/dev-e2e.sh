#!/usr/bin/env bash
# scripts/dev-e2e.sh — single source of truth for the local + CI end-to-end roundtrip.
#
# Boots compose (LLM_MODE=dry_run, deterministic embeddings), polls Agent Studio health
# with fast-fail diagnostics, runs scripts/dev_e2e.py against the live HTTP surface, then
# tears down. Used by the loop-engineering skill and the CI dev-e2e job so
# "works on my machine" == "works in CI".
#
# Usage:
#   scripts/dev-e2e.sh            # boot, run, tear down (teardown always runs)
#   scripts/dev-e2e.sh --no-down  # leave the stack up (handy for re-running the probe)
#
# Required env (defaults match compose.vps.example.yaml / ci-smoke):
#   SAGAD_POSTGRES_PASSWORD, AGENT_STUDIO_INTERNAL_SECRET,
#   SAGAD_INTEGRATION_ENCRYPTION_KEY, SAGAD_REALTIME_SECRET,
#   AUTH_SECRET (>=32 chars), AUTH_URL, SAGAD_WS_PUBLIC_URL, EMAIL_SERVER, EMAIL_FROM.
# CHATWOOT_WEBHOOK_TOKEN is set by this script so dev_e2e.py can exercise the token path.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

COMPOSE="${COMPOSE:-compose.vps.example.yaml}"
AGENT_STUDIO_CONTAINER="${AGENT_STUDIO_CONTAINER:-sagad-agent-studio}"
BASE_URL="${BASE_URL:-http://127.0.0.1:8010}"
NO_DOWN=0
for arg in "$@"; do
  case "$arg" in
    --no-down) NO_DOWN=1 ;;
    *) echo "unknown arg: $arg" >&2; exit 2 ;;
  esac
done

# Defaults that make the stack boot credential-free for the e2e roundtrip.
export SAGAD_POSTGRES_PASSWORD="${SAGAD_POSTGRES_PASSWORD:-sagad_dev_e2e}"
export AGENT_STUDIO_INTERNAL_SECRET="${AGENT_STUDIO_INTERNAL_SECRET:-dev-e2e-internal-secret}"
export SAGAD_INTEGRATION_ENCRYPTION_KEY="${SAGAD_INTEGRATION_ENCRYPTION_KEY:-dev-e2e-fernet-key-must-be-32-bytes}"
export SAGAD_REALTIME_SECRET="${SAGAD_REALTIME_SECRET:-dev-e2e-realtime-secret}"
export AUTH_SECRET="${AUTH_SECRET:-dev-e2e-auth-secret-must-be-at-least-32-chars}"
export AUTH_URL="${AUTH_URL:-http://localhost:3000}"
export SAGAD_WS_PUBLIC_URL="${SAGAD_WS_PUBLIC_URL:-http://localhost:3000}"
export EMAIL_SERVER="${EMAIL_SERVER:-smtp://localhost:1025}"
export EMAIL_FROM="${EMAIL_FROM:-dev-e2e@sagad-os.local}"
# Deterministic stub model + deterministic embeddings => no OpenAI key, no GPU, reproducible.
export LLM_MODE="dry_run"
export OPENAI_API_KEY="${OPENAI_API_KEY:-}"
# Chatwoot webhook token is read by the app AND by dev_e2e.py (via ?token=).
export CHATWOOT_WEBHOOK_TOKEN="${CHATWOOT_WEBHOOK_TOKEN:-dev-e2e-cw-token}"

teardown() {
  status=$?
  if [ "$status" -ne 0 ]; then
    echo "=== FAILURE — diagnostics ===" >&2
    docker compose -f "$COMPOSE" ps --format json >&2 || true
    docker inspect "$AGENT_STUDIO_CONTAINER" \
      --format '{{.State.Health.Status}} {{json .State.Health.Log}}' >&2 || true
    docker compose -f "$COMPOSE" logs --no-color --tail=120 sagad-agent-studio sagad-db >&2 || true
  fi
  if [ "$NO_DOWN" -eq 1 ]; then
    echo "--no-down: leaving stack up"
  else
    docker compose -f "$COMPOSE" down -v --remove-orphans >/dev/null 2>&1 || true
    docker network rm client_internal_network >/dev/null 2>&1 || true
  fi
  exit "$status"
}
trap teardown EXIT

echo "== dev-e2e: boot compose ($COMPOSE, LLM_MODE=dry_run) =="
docker network create client_internal_network >/dev/null 2>&1 || true
docker compose -f "$COMPOSE" config --quiet
docker compose -f "$COMPOSE" build sagad-agent-studio sagad-db
docker compose -f "$COMPOSE" up -d --wait --wait-timeout 240

echo "== dev-e2e: poll health =="
ready=0
for _ in $(seq 1 30); do
  if curl -fsS "$BASE_URL/health/ready" >/dev/null 2>&1; then
    ready=1; break
  fi
  sleep 2
done
if [ "$ready" -ne 1 ]; then
  echo "Agent Studio never became ready" >&2
  exit 1
fi
curl -fsS "$BASE_URL/health/live" >/dev/null
curl -fsS "$BASE_URL/health/ready" >/dev/null
echo "  health: live + ready 200"

echo "== dev-e2e: run roundtrip (scripts/dev_e2e.py) =="
INTERNAL_SECRET="$AGENT_STUDIO_INTERNAL_SECRET" \
CHATWOOT_WEBHOOK_TOKEN="$CHATWOOT_WEBHOOK_TOKEN" \
BASE_URL="$BASE_URL" \
uv run --project agent-studio python scripts/dev_e2e.py

echo "== dev-e2e: ALL GREEN =="