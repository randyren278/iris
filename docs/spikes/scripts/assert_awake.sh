#!/bin/bash
# CP-1.4 verifier: assert the chosen stay-awake mechanism is in effect.
#
# Chosen mechanism (see SPIKE-RESULTS.md, "CP-1.4 mechanism:"): the launchd job
# runs the daemon under `/usr/bin/caffeinate -i -s`, which holds a
# PreventUserIdleSystemSleep power assertion for exactly as long as the daemon
# lives. No permanent pmset change.
#
# Two modes:
#   live      — ~/.iris/caffeinate.pid exists: assert THAT process owns a
#               PreventUserIdleSystemSleep assertion right now.
#   self-test — no daemon yet: start `caffeinate -i -s -t 10`, prove the
#               assertion appears under its pid, kill it, prove it is released.
#
#   bash spikes/assert_awake.sh
set -uo pipefail

PIDFILE="${IRIS_CAFFEINATE_PIDFILE:-$HOME/.iris/caffeinate.pid}"

# Does <pid> currently own a PreventUserIdleSystemSleep assertion?
holds_assertion() {
    /usr/bin/pmset -g assertions \
        | grep -E "^[[:space:]]*pid $1\(caffeinate\):" \
        | grep -q 'PreventUserIdleSystemSleep'
}

if [ -f "$PIDFILE" ]; then
    pid=$(cat "$PIDFILE")
    echo "assert_awake: live mode, guard pid $pid from $PIDFILE"
    if ! kill -0 "$pid" 2>/dev/null; then
        echo "assert_awake: FAIL - guard pid $pid is not running" >&2
        exit 1
    fi
    if ! holds_assertion "$pid"; then
        echo "assert_awake: FAIL - pid $pid holds no PreventUserIdleSystemSleep assertion" >&2
        /usr/bin/pmset -g assertions | grep -i caffeinate >&2
        exit 1
    fi
    echo "assert_awake: PASS - pid $pid is holding PreventUserIdleSystemSleep"
    exit 0
fi

echo "assert_awake: no $PIDFILE, running self-test of the mechanism"
/usr/bin/caffeinate -i -s -t 10 &
guard=$!
# pmset publishes the assertion a beat after the process starts.
for _ in 1 2 3 4 5 6 7 8 9 10; do
    holds_assertion "$guard" && break
    sleep 0.5
done

if ! holds_assertion "$guard"; then
    echo "assert_awake: FAIL - caffeinate -i -s (pid $guard) never registered" >&2
    /usr/bin/pmset -g assertions | grep -i caffeinate >&2
    kill "$guard" 2>/dev/null
    exit 1
fi
echo "assert_awake: caffeinate -i -s (pid $guard) holds PreventUserIdleSystemSleep"
/usr/bin/pmset -g assertions | grep -A1 "pid $guard(caffeinate)"

kill "$guard" 2>/dev/null
wait "$guard" 2>/dev/null
for _ in 1 2 3 4 5 6; do
    holds_assertion "$guard" || break
    sleep 0.5
done
if holds_assertion "$guard"; then
    echo "assert_awake: FAIL - assertion survived the guard process" >&2
    exit 1
fi
echo "assert_awake: PASS - assertion released when the guard exited (scoped to daemon lifetime)"
exit 0
