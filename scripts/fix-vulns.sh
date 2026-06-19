#!/usr/bin/env bash
# =============================================================================
# scripts/fix-vulns.sh — automated npm HIGH/CRITICAL vulnerability fixer
#
# Written for LLMs/agents to read and run. Detects HIGH/CRITICAL advisories in
# an npm workspace, bumps the affected packages to their npm-recommended fixed
# versions (direct deps + an overrides entry to cover transitive deps), reinstalls,
# re-audits, and optionally verifies the workspace still lints/builds. On a clean
# result it leaves the changes staged in the working tree for scripts/pr.sh to ship.
#
# This automates exactly the kind of fix a trivy/`npm audit` HIGH finding asks for
# (e.g. nodemailer 7.0.13 -> 9.0.1): bump direct dep + add override + reinstall +
# verify, with no force-installs and no --no-verify.
#
# USAGE
#   scripts/fix-vulns.sh [--workspace v1] [--level high] [--verify] [--dry-run]
#
# ARGS
#   --workspace   npm project dir relative to repo root (default v1).
#   --level        audit level to gate on: high (default) or critical.
#   --verify       after fixing, run `npm run lint` and `npm run build` (if those
#                  scripts exist) to prove the bump didn't break the workspace.
#                  If a verify step fails, the fix is left in place but the script
#                  exits 1 so the agent does NOT ship a broken change.
#   --dry-run      audit + print the planned bumps, do not modify package.json or
#                  run npm install.
#
# EXIT CODES
#   0  no fixable vulns at the requested level (or dry-run printed a plan)
#   1  preflight error, or remaining HIGH/CRITICAL after fix, or verify failed
#
# NOTES
#   - Only acts on advisories npm reports as fixable. "No fix available" cases
#     (e.g. a vuln only in a transitive the parent won't upgrade) are reported and
#     skipped — the agent handles those manually (custom override, replace dep).
#   - Major-version fixes (isSemVerMajor) are applied but flagged; --verify is
#     the safety net.
#   - Never runs `npm audit fix --force` (that downgrades/breaks unrelated deps).
# =============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$REPO_DIR"

WORKSPACE="v1"
LEVEL="high"
VERIFY=0
DRY_RUN=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --workspace) WORKSPACE="$2"; shift 2 ;;
    --level)     LEVEL="$2"; shift 2 ;;
    --verify)    VERIFY=1; shift ;;
    --dry-run)   DRY_RUN=1; shift ;;
    -h|--help)
      sed -n '2,/^=====/p' "$0" | sed 's/^# \{0,1\}//'
      exit 0
      ;;
    *) echo "fix-vulns.sh: unknown argument: $1" >&2; exit 1 ;;
  esac
done

say()  { echo "fix-vulns.sh: $*"; }
err()  { echo "fix-vulns.sh: $*" >&2; }

case "$LEVEL" in
  high|critical) ;;
  *) err "--level must be high or critical"; exit 1 ;;
esac

PKG_DIR="$REPO_DIR/$WORKSPACE"
if [[ ! -f "$PKG_DIR/package.json" ]]; then
  err "no package.json found at $PKG_DIR (use --workspace <dir>)"
  exit 1
fi

if ! command -v node >/dev/null 2>&1 || ! command -v npm >/dev/null 2>&1; then
  err "node and npm are required"
  exit 1
fi

say "workspace: $WORKSPACE  level: $LEVEL"

# --- 1. audit ----------------------------------------------------------------
AUDIT_JSON="$PKG_DIR/.audit.json"
trap 'rm -f "$AUDIT_JSON"' EXIT

say "running npm audit"
( cd "$PKG_DIR" && npm audit --json --audit-level="$LEVEL" > "$AUDIT_JSON" 2>/dev/null ) || true

# --- 2. parse the audit into a fix plan (node) -------------------------------
PLAN="$(
  node - "$AUDIT_JSON" "$LEVEL" "$PKG_DIR" <<'NODE'
const fs = require("fs");
const { execSync } = require("child_process");
const path = process.argv[2];
const level = process.argv[3] || "high";
const cwd = process.argv[4];
const ranks = { low: 1, moderate: 2, high: 3, critical: 4 };
const minRank = ranks[level] || 3;
let data;
try { data = JSON.parse(fs.readFileSync(path, "utf8")); } catch { data = {}; }

// npm audit --json shape: data.vulnerabilities = { name: { severity, fixAvailable, ... } }
const vulns = data.vulnerabilities || {};
const fixes = [];
const noFix = [];
function latestVersion(name) {
  try {
    return execSync(`npm view ${name} version`, { cwd, encoding: "utf8", stdio: ["ignore","pipe","ignore"] }).trim();
  } catch { return null; }
}
for (const [name, v] of Object.entries(vulns)) {
  const sev = (v.severity || "").toLowerCase();
  if ((ranks[sev] || 0) < minRank) continue;
  const fa = v.fixAvailable;
  if (fa && typeof fa === "object") {
    fixes.push({ name, severity: sev, fixVersion: fa.version, isSemVerMajor: !!fa.isSemVerMajor });
  } else if (fa === true) {
    // npm can fix it via `npm audit fix` (likely non-major).
    fixes.push({ name, severity: sev, fixVersion: null, isSemVerMajor: false, auditFix: true });
  } else if (fa === false) {
    // npm won't auto-fix (typically a major-version security bump).
    // Resolve the package's latest published version as the fix target.
    const latest = latestVersion(name);
    if (latest) fixes.push({ name, severity: sev, fixVersion: latest, isSemVerMajor: true, wasNoFix: true });
    else noFix.push({ name, severity: sev, reason: "could not resolve a fixed version" });
  } else {
    noFix.push({ name, severity: sev });
  }
}
console.log(JSON.stringify({ fixes, noFix }, null, 0));
NODE
)"

FIXES="$(node -e "const p=JSON.parse(process.argv[1]); console.log(JSON.stringify(p.fixes))" "$PLAN")"
NOFIX="$(node -e "const p=JSON.parse(process.argv[1]); console.log(JSON.stringify(p.noFix))" "$PLAN")"
FIX_COUNT="$(node -e "const p=JSON.parse(process.argv[1]); console.log(p.length)" "$FIXES" 2>/dev/null || echo 0)"

if [[ -n "$NOFIX" && "$NOFIX" != "[]" ]]; then
  say "note: unfixable-by-npm advisories at $LEVEL (handle manually):"
  echo "$NOFIX" | node -e "let s='';process.stdin.on('data',d=>s+=d).on('end',()=>{for(const x of JSON.parse(s))console.log('  - '+x.name+' ('+x.severity+')')})"
fi

if [[ "$FIX_COUNT" -eq 0 ]]; then
  say "no fixable $LEVEL+ vulnerabilities in $WORKSPACE"
  exit 0
fi

say "planned fixes:"
echo "$FIXES" | node -e "
let s='';process.stdin.on('data',d=>s+=d).on('end',()=>{
  for(const f of JSON.parse(s)){
    const tgt = f.fixVersion ? ('^'+f.fixVersion) : 'npm audit fix';
    const major = f.isSemVerMajor ? ' [MAJOR bump]' : '';
    const nofix = f.wasNoFix ? ' (npm reported no-fix; bumped to latest)' : '';
    console.log('  - '+f.name+' ('+f.severity+') -> '+tgt+major+nofix);
  }
})"

if [[ "$DRY_RUN" -eq 1 ]]; then
  say "DRY RUN — package.json not modified."
  exit 0
fi

# --- 3. apply bumps to package.json (direct dep + override) ------------------
say "applying bumps to package.json"
node - "$PKG_DIR/package.json" "$FIXES" <<'NODE'
const fs = require("fs");
const path = process.argv[2];
const fixes = JSON.parse(process.argv[3]);
const pkg = JSON.parse(fs.readFileSync(path, "utf8"));
pkg.overrides = pkg.overrides || {};
for (const f of fixes) {
  if (!f.fixVersion) continue; // audit-fix-only: leave for `npm audit fix` step
  const target = "^" + f.fixVersion;
  if (pkg.dependencies && Object.prototype.hasOwnProperty.call(pkg.dependencies, f.name)) {
    pkg.dependencies[f.name] = target;
  } else if (pkg.devDependencies && Object.prototype.hasOwnProperty.call(pkg.devDependencies, f.name)) {
    pkg.devDependencies[f.name] = target;
  }
  // always (re)assert an override so transitive deps are forced to the fixed version
  pkg.overrides[f.name] = target;
}
fs.writeFileSync(path, JSON.stringify(pkg, null, 2) + "\n");
NODE

# pick up advisories that only need `npm audit fix` (non-major, no explicit version)
NEEDS_AUDIT_FIX="$(node - "$FIXES" <<'NODE'
const fixes = JSON.parse(process.argv[2]);
process.stdout.write(fixes.some((f) => !f.fixVersion) ? "true" : "false");
NODE
)"

say "reinstalling"
( cd "$PKG_DIR" && npm install --no-audit >/dev/null )

if [[ "$NEEDS_AUDIT_FIX" == "true" ]]; then
  say "running npm audit fix for non-major advisories"
  ( cd "$PKG_DIR" && npm audit fix --no-audit >/dev/null ) || true
fi

# --- 4. re-audit -------------------------------------------------------------
say "re-running npm audit"
( cd "$PKG_DIR" && npm audit --json --audit-level="$LEVEL" > "$AUDIT_JSON" 2>/dev/null ) || true
REMAIN="$(node - "$AUDIT_JSON" "$LEVEL" <<'NODE'
const fs = require("fs");
const ranks = { low:1, moderate:2, high:3, critical:4 };
const min = ranks[process.argv[3]] || 3;
let data; try { data = JSON.parse(fs.readFileSync(process.argv[2],"utf8")); } catch { data = {}; }
const out = [];
for (const [name, v] of Object.entries(data.vulnerabilities || {})) {
  if ((ranks[(v.severity||"").toLowerCase()]||0) >= min) out.push(name);
}
console.log(out.join(","));
NODE
)"

if [[ -n "$REMAIN" ]]; then
  err "remaining $LEVEL+ vulnerabilities after fix: $REMAIN"
  err "these are not auto-fixable; resolve manually (custom override or replace the dependency)."
  exit 1
fi
say "no $LEVEL+ vulnerabilities remain"

# --- 5. optional verify ------------------------------------------------------
if [[ "$VERIFY" -eq 1 ]]; then
  say "verifying workspace still lints + builds"
  if ( cd "$PKG_DIR" && node -e "const p=require('./package.json');process.exit(p.scripts&&p.scripts.lint?0:1)" ); then
    ( cd "$PKG_DIR" && npm run lint ) || { err "lint failed after bump — NOT shipping"; exit 1; }
  fi
  if ( cd "$PKG_DIR" && node -e "const p=require('./package.json');process.exit(p.scripts&&p.scripts.build?0:1)" ); then
    ( cd "$PKG_DIR" && npm run build ) || { err "build failed after bump — NOT shipping"; exit 1; }
  fi
  say "verify passed"
fi

say "done. changes are in $WORKSPACE/package.json + lockfile — stage and run scripts/pr.sh."