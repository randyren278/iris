#!/usr/bin/env bash
set -euo pipefail

root="$(cd "$(dirname "$0")/.." && pwd)"
target="$HOME/Library/LaunchAgents/com.iris.gateway.plist"
label="com.iris.gateway"
domain="gui/$(id -u)"
claude_bin="$(dirname "$(command -v claude)")"
codex_bin="$(dirname "$(command -v codex)")"
daemon_path="$claude_bin:$codex_bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"
health_attempts="${IRIS_INSTALL_HEALTH_ATTEMPTS:-30}"
health_sleep="${IRIS_INSTALL_HEALTH_SLEEP_SECONDS:-1}"
mkdir -p "$(dirname "$target")"
cat > "$target" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>com.iris.gateway</string>
  <key>ProgramArguments</key><array><string>$root/.venv/bin/python</string><string>-m</string><string>iris.main</string></array>
  <key>WorkingDirectory</key><string>$root</string>
  <key>KeepAlive</key><true/>
  <key>RunAtLoad</key><true/>
  <key>ThrottleInterval</key><integer>10</integer>
  <key>ProcessType</key><string>Background</string>
  <key>StandardOutPath</key><string>$HOME/.iris/launchd.out.log</string>
  <key>StandardErrorPath</key><string>$HOME/.iris/launchd.err.log</string>
  <key>EnvironmentVariables</key><dict><key>PATH</key><string>$daemon_path</string></dict>
</dict></plist>
PLIST
chmod 600 "$target"
plutil -lint "$target" >/dev/null
mkdir -p "$HOME/.iris"
chmod 700 "$HOME/.iris"
launchctl bootout "$domain/$label" 2>/dev/null || true
bootstrapped=false
for attempt in 1 2 3 4 5; do
  if launchctl bootstrap "$domain" "$target" 2>/dev/null; then
    bootstrapped=true
    break
  fi
  # bootout returns before launchd always releases the old label.
  sleep 1
done
[ "$bootstrapped" = true ] || { echo "Could not bootstrap $label after 5 attempts." >&2; exit 1; }
launchctl enable "$domain/$label" 2>/dev/null || true
launchctl kickstart -k "$domain/$label"

# Deploy the menu-bar control plane from this exact checkout before judging the
# daemon. If health fails, SwiftBar still has the current plugin and can surface
# the failure instead of leaving an older copy installed.
"$root/scripts/menubar/install-plugin.sh" install

online=false
for ((attempt=1; attempt<=health_attempts; attempt++)); do
  if "$root/.venv/bin/python" -m iris.irisctl verify-online >/dev/null 2>&1; then
    online=true
    break
  fi
  sleep "$health_sleep"
done

if [ "$online" != true ]; then
  echo "Iris launchd job was installed but did not reach a healthy Socket Mode heartbeat." >&2
  echo "Check: $root/.venv/bin/python -m iris.irisctl status" >&2
  if [ -f "$HOME/.iris/launchd.err.log" ]; then
    echo "--- recent launchd errors ---" >&2
    tail -n 20 "$HOME/.iris/launchd.err.log" >&2 || true
  fi
  exit 1
fi

echo "Iris installed, current menu bar plugin deployed, and Socket Mode is online."
