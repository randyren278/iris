#!/bin/bash
# Runs each live probe in sequence against real dependencies (Keychain, Slack
# Socket Mode, EventKit, a real claude subprocess) and appends real output to
# .review/live-evidence.md. Exits non-zero on the first failure.
set -u

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$REPO_ROOT"

EVIDENCE=".review/live-evidence.md"
PY=".venv/bin/python"

mkdir -p .review
echo "# Live Evidence" > "$EVIDENCE"
echo "" >> "$EVIDENCE"
echo "Recorded: $(date -u +%Y-%m-%dT%H:%M:%SZ)" >> "$EVIDENCE"

run_probe() {
    local name="$1"
    shift
    echo "" >> "$EVIDENCE"
    echo "## $name" >> "$EVIDENCE"
    echo '```' >> "$EVIDENCE"
    echo "\$ $*" >> "$EVIDENCE"
    local output
    output="$("$@" 2>&1)"
    local status=$?
    echo "$output" >> "$EVIDENCE"
    echo "(exit $status)" >> "$EVIDENCE"
    echo '```' >> "$EVIDENCE"
    if [ "$status" -ne 0 ]; then
        echo "FAILED: $name (exit $status)" >&2
        echo "$output" >&2
        return "$status"
    fi
    echo "OK: $name"
    return 0
}

# No `timeout(1)` on this Mac; a bare macOS box has no coreutils. Bound a
# probe with a background watchdog instead so a hung permission dialog can't
# stall the gate forever.
run_with_timeout() {
    local seconds="$1"
    shift
    "$@" &
    local cmd_pid=$!
    ( sleep "$seconds" && kill -9 "$cmd_pid" 2>/dev/null ) &
    local watchdog_pid=$!
    local status
    wait "$cmd_pid" 2>/dev/null
    status=$?
    kill "$watchdog_pid" 2>/dev/null
    wait "$watchdog_pid" 2>/dev/null
    return "$status"
}

run_probe "Keychain credential read" \
    "$PY" -c "from iris.slack_config import load_credentials as l; c=l(); print('CREDS_OK' if c.app_token and c.bot_token else 'CREDS_MISSING')" \
    || exit 1

run_probe "Slack Socket Mode authentication" \
    "$PY" -m iris.slack_probe \
    || exit 1

run_probe "EventKit calendar read (read-only, 40s timeout)" \
    run_with_timeout 40 "$PY" -m iris.senses.calendar_probe \
    || exit 1

run_probe "Claude approval hook fires under isolation" \
    "$PY" -m iris.hook_probe \
    || exit 1

echo "All live probes passed. Evidence in $EVIDENCE"
exit 0
