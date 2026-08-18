#!/bin/bash
#
# iris.30s.sh — SwiftBar plugin for the Iris Slack gateway daemon.
#
# Install:
#   ./scripts/install.sh    # installs the launchd daemon and this plugin together
# By hand:
#   cp scripts/menubar/iris.30s.sh ~/.swiftbar-plugins/
#   chmod +x ~/.swiftbar-plugins/iris.30s.sh
#
# The 30s in the filename = SwiftBar re-runs this every 30 seconds. The daemon
# heartbeats every 20s, so a state change surfaces within about half a minute.
#
# This is a pure reader. It opens exactly one file, ~/.iris/runtime.json, which
# carries daemon health only: no message text, no prompts, no credentials. It
# never writes, and the one action it offers is the documented launchd restart.
#
# Everything before the first "---" is the menu-bar line; lines after it are the
# dropdown. "| bash=... terminal=false refresh=true" runs a shell action.
#
# IRIS_STATE_DIR overrides the state directory. Production never sets it; the
# test suite does, which is how every state below is verified without a daemon.

STATE_DIR="${IRIS_STATE_DIR:-$HOME/.iris}"
STATUS="$STATE_DIR/runtime.json"
ERRLOG="$STATE_DIR/launchd.err.log"
LABEL="com.iris.gateway"

# Must equal the max_age default of StatusStore.healthy() in iris/runtime.py, or
# this icon and `irisctl verify-online` will disagree about the same daemon.
# tests/test_menubar_plugin.py reads that default and asserts it matches.
STALE_AFTER_SECONDS=90

footer() {
  echo "---"
  echo "Restart Iris | bash=/bin/launchctl param1=kickstart param2=-k param3=gui/$(id -u)/$LABEL terminal=false refresh=true"
  echo "Open error log | bash=/usr/bin/open param1=-a param2=Console param3=$ERRLOG terminal=false"
  echo "Refresh | refresh=true"
}

is_number() {
  case "$1" in
    '' | *[!0-9]*) return 1 ;;
    *) return 0 ;;
  esac
}

# --- epoch -> "3m ago", or "never this boot" for a null/absent timestamp ---
since() {
  local value="${1%%.*}"
  is_number "$value" || { echo "never this boot"; return; }
  local seconds=$(( $(date +%s) - value ))
  [ "$seconds" -lt 0 ] && seconds=0
  if [ "$seconds" -lt 60 ]; then
    echo "${seconds}s ago"
  elif [ "$seconds" -lt 3600 ]; then
    echo "$((seconds / 60))m ago"
  elif [ "$seconds" -lt 86400 ]; then
    echo "$((seconds / 3600))h $(((seconds % 3600) / 60))m ago"
  else
    echo "$((seconds / 86400))d ago"
  fi
}

# --- no runtime record: nothing has ever run against this state directory ---
if [ ! -f "$STATUS" ]; then
  echo "◉ | color=gray"
  echo "---"
  echo "IRIS · Slack gateway | size=11 color=gray"
  echo "Not running — no runtime record | color=gray"
  footer
  exit 0
fi

# --- parse runtime.json (jq when present, python3 otherwise) ---
read_json() {
  if command -v jq >/dev/null 2>&1; then
    jq -r "$1 // \"\"" "$STATUS" 2>/dev/null
  else
    python3 -c "import json; d = json.load(open('$STATUS')); v = d.get('$2'); print('' if v is None else v)" 2>/dev/null
  fi
}

STATE=$(read_json '.state' 'state')
PID=$(read_json '.pid' 'pid')
BOOT=$(read_json '.boot_id' 'boot_id')
UPDATED=$(read_json '.updated_at' 'updated_at')
INBOUND=$(read_json '.last_inbound_at' 'last_inbound_at')
OUTBOUND=$(read_json '.last_outbound_at' 'last_outbound_at')
ERR=$(read_json '.last_error' 'last_error')

AGE=""
if is_number "${UPDATED%%.*}"; then
  AGE=$(( $(date +%s) - ${UPDATED%%.*} ))
  [ "$AGE" -lt 0 ] && AGE=0
fi

# --- unreadable: a corrupt or half-written record is not a verdict either way.
# StatusStore writes atomically, so this should only ever mean real corruption.
if [ -z "$STATE" ] || [ -z "$AGE" ] || ! is_number "$PID"; then
  echo "◉ | color=orange"
  echo "---"
  echo "IRIS · Slack gateway | size=11 color=gray"
  echo "runtime.json unreadable — the next heartbeat rewrites it | color=orange"
  footer
  exit 0
fi

# --- verdict ---
if [ "$STATE" = "offline" ]; then
  COLOR=red
  HEADLINE="Offline — disconnected $(since "$UPDATED")"
elif ! kill -0 "$PID" 2>/dev/null; then
  # A SIGKILLed daemon leaves state "online" on disk forever. Without this the
  # icon would stay green for a full staleness window over a dead process.
  COLOR=red
  HEADLINE="Not running — PID $PID is gone"
elif [ "$STATE" = "starting" ]; then
  COLOR=orange
  HEADLINE="Starting — no Socket Mode connection yet"
elif [ "$STATE" = "online" ] && [ "$AGE" -le "$STALE_AFTER_SECONDS" ]; then
  COLOR=green
  HEADLINE="Online — heartbeat $(since "$UPDATED")"
elif [ "$STATE" = "online" ]; then
  COLOR=orange
  HEADLINE="Stale — last heartbeat $(since "$UPDATED")"
else
  COLOR=orange
  HEADLINE="Unrecognized state: $STATE"
fi

echo "◉ | color=$COLOR"
echo "---"
echo "IRIS · Slack gateway | size=11 color=gray"
echo "$HEADLINE | color=$COLOR"
[ -n "$ERR" ] && echo "Last error: $ERR | color=orange"
echo "---"
echo "Last message in: $(since "$INBOUND")"
echo "Last message out: $(since "$OUTBOUND")"
echo "---"
echo "PID $PID · boot ${BOOT:0:8} | size=11 color=gray"
footer
exit 0
