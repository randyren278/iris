#!/usr/bin/env bash
set -euo pipefail

root="$(cd "$(dirname "$0")/.." && pwd)"
target="$HOME/Library/LaunchAgents/com.iris.gateway.plist"
label="com.iris.gateway"
domain="gui/$(id -u)"
claude_bin="$(dirname "$(command -v claude)")"
codex_bin="$(dirname "$(command -v codex)")"
daemon_path="$claude_bin:$codex_bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"
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
"$root/scripts/menubar/install-plugin.sh" install
echo "Iris installed and started. Check: python -m iris.irisctl status"
