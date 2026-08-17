#!/usr/bin/env bash
# hera_e2e_scratch.sh — run Hera's full e2e suite against a disposable copy.
#
# Hera's suite is clean-state by design: `e2e_final.sh --step setup` and
# `e2e_ingest.sh` both delete hera.db and wiki/, and each resolves its target
# from its own location with no environment override. Running the suite in the
# installed vault therefore either destroys real notes or (since e2e_guard.sh)
# is refused outright with exit 3.
#
# So the only way to run it for real is against a copy. This script makes one,
# runs `--all` there, and removes it. The live vault is never the target, which
# is also why the guard permits the run: a scratch copy is by construction not
# the path named in the locator.
#
# Exit codes: 0 all steps passed · non-zero the suite failed (code propagated).
set -euo pipefail

HERA="${HERA_SRC:-/Users/randyren/Developer/second brain/hera}"
SCRATCH="${SCRATCH_DIR:-${CLAUDE_JOB_DIR:-/tmp}/tmp/hera-e2e-cp26}"

[ -d "$HERA" ] || { echo "no Hera repo at: $HERA" >&2; exit 2; }

cleanup() { [ "${KEEP_SCRATCH:-0}" = "1" ] || rm -rf "$SCRATCH"; }
trap cleanup EXIT

rm -rf "$SCRATCH"
mkdir -p "$(dirname "$SCRATCH")"

# Copy everything except git history and the caches that would be rebuilt
# anyway. .venv IS copied: its interpreter symlink is absolute, so the copy
# works, and rebuilding it per run would dominate the runtime.
rsync -a \
  --exclude '.git/' \
  --exclude '__pycache__/' \
  --exclude '*.pyc' \
  "$HERA"/ "$SCRATCH"/

# Prove isolation before running anything destructive. If the locator still
# points at the live vault from inside the copy, abort rather than find out
# the hard way.
LIVE_REAL="$(cd "$HERA" && pwd -P)"
SCRATCH_REAL="$(cd "$SCRATCH" && pwd -P)"
[ "$LIVE_REAL" != "$SCRATCH_REAL" ] || { echo "scratch resolved to the live vault" >&2; exit 2; }

# Deliberately DO NOT export HERA_VAULT here, and unset any inherited value.
#
# e2e_guard.sh treats $HERA_VAULT as authoritative for "which vault is live".
# Pinning it to the scratch path makes the copy look like the live vault, so the
# guard refuses its own scratch run (observed: exit 3). Leaving it unset lets the
# scripts self-locate from $0/.. — which resolves to this copy — while the guard
# compares against ~/.claude/hera.env, which still names the real vault. The two
# paths then differ, which is exactly the condition the guard permits.
# Always tee to a stable path. The suite takes minutes, so a failure that is
# only visible in a caller's captured stdout is expensive to reproduce; the
# checkpoint runner in particular discards output on the happy path.
LOG="${LOG_PATH:-${CLAUDE_JOB_DIR:-/tmp}/tmp/hera-e2e-cp26.log}"
mkdir -p "$(dirname "$LOG")"

cd "$SCRATCH"
set +e
env -u HERA_VAULT bash scripts/e2e_final.sh --all 2>&1 | tee "$LOG"
rc=${PIPESTATUS[0]}
set -e
[ "$rc" -eq 0 ] || echo "suite failed (rc=$rc); full log: $LOG" >&2
exit "$rc"
