#!/usr/bin/env bash
# =============================================================================
# scripts/pr.sh — agent-driven PR submitter
#
# This script is written for LLMs/agents to read and run. It automates the
# mechanical parts of shipping a change: branch off latest origin/main,
# move the current working-tree changes onto that branch, commit, push, and
# open a pull request with a body that wraps the agent's summary in the
# repo's PR template.
#
# The agent's job: write the title and the Summary body. This script's job:
# submit them safely.
#
# USAGE
#   scripts/pr.sh --title "<PR title>" --body-file <path> \
#     [--branch <slug>] [--prefix feat] [--commit-msg "<msg>"] \
#     [--base main] [--dry-run]
#
# ARGS
#   --title        (required) PR title.
#   --body-file    (required) markdown file = the PR Summary content (agent-written).
#   --branch        branch slug without prefix. Default: slugified title.
#   --prefix        branch prefix (default feat) -> "<prefix>/<slug>".
#   --commit-msg    git commit message (default: the title).
#   --base          PR base branch (default main).
#   --dry-run       do everything locally (branch, move, commit) but do NOT
#                   push or open the PR. Prints what it would do.
#
# SAFETY CONTRACT (read this before running)
#   - Never force-pushes. Never uses --no-verify. Hooks always run.
#   - Never commits .env (refuses if .env is staged/untracked).
#   - Refuses to run while on main/master.
#   - On any mid-flow failure, restores the original branch and the stash so
#     no work is lost.
#   - set -euo pipefail; all paths quoted. Works on Git Bash (Windows) and ubuntu.
#
# EXIT CODES
#   0 success (or dry-run completed)
#   1 preflight or user error
#   2 stash/checkout/pop conflict (work restored, nothing lost)
# =============================================================================
set -euo pipefail

# --- repo location (script works from any cwd) -------------------------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$REPO_DIR"

# --- defaults ----------------------------------------------------------------
TITLE=""
BODY_FILE=""
BRANCH=""
PREFIX="feat"
COMMIT_MSG=""
BASE="main"
DRY_RUN=0

# --- arg parsing -------------------------------------------------------------
while [[ $# -gt 0 ]]; do
  case "$1" in
    --title)       TITLE="$2"; shift 2 ;;
    --body-file)   BODY_FILE="$2"; shift 2 ;;
    --branch)      BRANCH="$2"; shift 2 ;;
    --prefix)      PREFIX="$2"; shift 2 ;;
    --commit-msg)  COMMIT_MSG="$2"; shift 2 ;;
    --base)        BASE="$2"; shift 2 ;;
    --dry-run)     DRY_RUN=1; shift ;;
    -h|--help)
      sed -n '2,/^=====/p' "$0" | sed 's/^# \{0,1\}//'
      exit 0
      ;;
    *)
      echo "pr.sh: unknown argument: $1" >&2
      exit 1
      ;;
  esac
done

# --- helpers -----------------------------------------------------------------
err()  { echo "pr.sh: $*" >&2; }
say()  { echo "pr.sh: $*"; }

require_arg() {
  local name="$1" val="$2"
  if [[ -z "$val" ]]; then
    err "missing required --$name"
    exit 1
  fi
}

slugify() {
  # lowercase, collapse non [a-z0-9] runs to "-", trim dashes at ends
  local s="$1"
  s="$(echo "$s" | tr '[:upper:]' '[:lower:]')"
  s="$(echo "$s" | tr -c 'a-z0-9' '-' )"
  s="${s#-}"
  s="${s%-}"
  s="$(echo "$s" | tr -s '-')"
  echo "$s"
}

require_arg title "$TITLE"
require_arg body-file "$BODY_FILE"

if [[ ! -f "$BODY_FILE" ]]; then
  err "--body-file not found: $BODY_FILE"
  exit 1
fi

: "${COMMIT_MSG:=$TITLE}"

if [[ -z "$BRANCH" ]]; then
  BRANCH="$(slugify "$TITLE")"
fi
if [[ -z "$BRANCH" ]]; then
  err "could not derive branch name from title; pass --branch"
  exit 1
fi
FULL_BRANCH="${PREFIX}/${BRANCH}"

# --- preflight ---------------------------------------------------------------
say "preflight"

# git present and inside a repo
if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  err "not inside a git repository"
  exit 1
fi

# must NOT be on main/master
CURRENT_BRANCH="$(git rev-parse --abbrev-ref HEAD)"
if [[ "$CURRENT_BRANCH" == "main" || "$CURRENT_BRANCH" == "master" ]]; then
  err "refusing to run while on $CURRENT_BRANCH. Switch to a working branch first."
  exit 1
fi

# gh installed + authenticated (only required when actually opening a PR)
if [[ "$DRY_RUN" -eq 0 ]]; then
  if ! command -v gh >/dev/null 2>&1; then
    err "gh CLI not found. Install GitHub CLI and run 'gh auth login'."
    exit 1
  fi
  if ! gh auth status >/dev/null 2>&1; then
    err "gh is not authenticated. Run 'gh auth login'."
    exit 1
  fi
fi

# there must be something to ship (tracked modifications OR untracked files)
if [[ -z "$(git status --porcelain)" ]]; then
  err "working tree is clean — nothing to ship."
  exit 1
fi

# .env must never be committed (secrets policy per AGENTS.md)
if git status --porcelain | grep -Eq '(^.. |^..)\.env$' ; then
  err "refusing: .env appears in the working-tree changes. Unstage/remove it before shipping."
  err "offending entries:"
  git status --porcelain | grep -E '\.env$' >&2 || true
  exit 1
fi

# fetch latest base
say "fetching origin/$BASE"
git fetch origin "$BASE" --quiet

# warn if the current branch has commits ahead of base that will NOT ship
AHEAD="$(git rev-list --count "origin/$BASE..HEAD" 2>/dev/null || echo 0)"
if [[ "$AHEAD" -gt 0 ]]; then
  say "note: current branch '$CURRENT_BRANCH' has $AHEAD commit(s) ahead of origin/$BASE."
  say "      Those commits will NOT be included in this PR — only the working-tree changes move over."
fi

# --- compose PR body ---------------------------------------------------------
TEMPLATE_FILE=".github/PULL_REQUEST_TEMPLATE.md"
BODY_TMP="$(mktemp -t pr-body.XXXXXX.md 2>/dev/null || mktemp)"
cleanup() {
  [[ -n "$BODY_TMP" && -f "$BODY_TMP" ]] && rm -f "$BODY_TMP"
  true
}
trap cleanup EXIT

{
  echo "## Summary"
  echo
  cat "$BODY_FILE"
  echo
  if [[ -f "$TEMPLATE_FILE" ]]; then
    echo "---"
    echo
    # Drop the template's own empty Summary header so we don't duplicate it.
    sed '/^## Summary$/d' "$TEMPLATE_FILE"
  fi
} > "$BODY_TMP"

# --- dry run: print the plan, mutate nothing ---------------------------------
if [[ "$DRY_RUN" -eq 1 ]]; then
  say "DRY RUN — no branches created, nothing committed, nothing pushed."
  say "  base:      $BASE (origin/$BASE)"
  say "  branch:    $FULL_BRANCH"
  say "  commit:    $COMMIT_MSG"
  say "  title:     $TITLE"
  say "  body file: $BODY_TMP"
  say "  would ship (working-tree changes):"
  git status --short | sed 's/^/    /'
  say "  would run:"
  say "    git stash push --include-untracked -m pr-ship"
  say "    git checkout -B $FULL_BRANCH origin/$BASE"
  say "    git stash pop"
  say "    git add -A && git commit -m \"$COMMIT_MSG\""
  say "    git push -u origin $FULL_BRANCH"
  say "    gh pr create --base $BASE --head $FULL_BRANCH --title \"$TITLE\" --body-file $BODY_TMP"
  say "preview composed body:"
  sed 's/^/    /' "$BODY_TMP"
  exit 0
fi

# --- move work onto a fresh main, then commit --------------------------------
# Stash everything (tracked + untracked), branch at origin/<base>, pop it back.
STASH_LABEL="pr-ship-$$"

say "stashing working-tree changes"
STASHED=0
if git stash push --include-untracked -m "$STASH_LABEL" >/dev/null 2>&1; then
  STASHED=1
fi

# restore original branch + stash on failure
abort_restore() {
  err "restoring original branch '$CURRENT_BRANCH' and stash..."
  git checkout "$CURRENT_BRANCH" >/dev/null 2>&1 || true
  if [[ "$STASHED" -eq 1 ]]; then
    git stash pop >/dev/null 2>&1 || git stash apply >/dev/null 2>&1 || true
  fi
}

say "creating branch '$FULL_BRANCH' at origin/$BASE"
if ! git checkout -B "$FULL_BRANCH" "origin/$BASE" >/dev/null 2>&1; then
  abort_restore
  err "failed to create/checkout branch '$FULL_BRANCH'"
  exit 2
fi

if [[ "$STASHED" -eq 1 ]]; then
  say "restoring stashed changes onto '$FULL_BRANCH'"
  if ! git stash pop >/dev/null 2>&1; then
    abort_restore
    err "conflict while restoring stashed changes onto origin/$BASE."
    err "your changes are still in the stash (git stash list) and on '$CURRENT_BRANCH'. Nothing is lost."
    err "resolve the conflict (the changes depend on commits not in $BASE) and re-run, or ship from the current branch instead."
    exit 2
  fi
fi

say "staging and committing"
git add -A
git commit -m "$COMMIT_MSG" >/dev/null

# short diffstat for the log
DIFFSTAT="$(git diff --stat "origin/$BASE..HEAD")"
say "committed on '$FULL_BRANCH':"
echo "$DIFFSTAT" | sed 's/^/  /'

# --- push + open PR ----------------------------------------------------------
say "pushing $FULL_BRANCH"
git push -u origin "$FULL_BRANCH"

say "opening pull request"
PR_URL="$(gh pr create \
  --base "$BASE" \
  --head "$FULL_BRANCH" \
  --title "$TITLE" \
  --body-file "$BODY_TMP")"

say "PR opened: $PR_URL"