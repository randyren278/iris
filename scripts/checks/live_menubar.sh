#!/usr/bin/env bash
set -euo pipefail

root="$(cd "$(dirname "$0")/../.." && pwd)"
source_plugin="$root/scripts/menubar/iris.30s.sh"
state_dir="${IRIS_STATE_DIR:-$HOME/.iris}"
label="com.iris.gateway"
domain="gui/$(id -u)"

if [ "$(uname -s)" != "Darwin" ]; then
  echo "live_menubar.sh must run on the operator Mac." >&2
  exit 2
fi

if [ ! -d "/Applications/SwiftBar.app" ]; then
  echo "SwiftBar is not installed in /Applications; menu-bar deployment cannot be certified." >&2
  exit 1
fi

plugin_dir="$(defaults read com.ameba.SwiftBar PluginDirectory 2>/dev/null || true)"
plugin_dir="${plugin_dir:-$HOME/.swiftbar-plugins}"
installed="$plugin_dir/iris.30s.sh"

[ -x "$installed" ] || { echo "Installed Iris SwiftBar plugin is missing or not executable: $installed" >&2; exit 1; }
cmp -s "$source_plugin" "$installed" || {
  echo "Installed Iris SwiftBar plugin is stale relative to this checkout. Re-run ./scripts/install.sh." >&2
  exit 1
}

launchctl print "$domain/$label" >/dev/null 2>&1 || {
  echo "launchd job $domain/$label is not loaded." >&2
  exit 1
}

"$root/.venv/bin/python" -m iris.irisctl verify-online >/dev/null || {
  echo "Iris launchd job is loaded but Socket Mode is not healthy." >&2
  exit 1
}

output="$(IRIS_STATE_DIR="$state_dir" /bin/bash "$installed")"
headline="$(printf '%s\n' "$output" | head -n 1)"
if [ -f "$state_dir/disarmed" ]; then
  printf '%s\n' "$output" | grep -F "Control: DISARMED" >/dev/null || {
    echo "Menu bar failed to surface the persistent disarm marker." >&2
    exit 1
  }
  printf '%s\n' "$headline" | grep -F "color=orange" >/dev/null || {
    echo "Healthy-but-disarmed Iris must render orange, not green." >&2
    exit 1
  }
else
  printf '%s\n' "$headline" | grep -F "color=green" >/dev/null || {
    echo "Healthy armed Iris did not render green in the installed plugin." >&2
    printf '%s\n' "$output" >&2
    exit 1
  }
fi

open -ga SwiftBar >/dev/null 2>&1 || {
  echo "SwiftBar could not be opened." >&2
  exit 1
}
for _attempt in 1 2 3 4 5 6 7 8 9 10; do
  pgrep -x SwiftBar >/dev/null 2>&1 && break
  sleep 0.5
done
pgrep -x SwiftBar >/dev/null 2>&1 || {
  echo "SwiftBar did not stay running after launch." >&2
  exit 1
}

echo "PASS: launchd is online, the installed SwiftBar plugin matches this checkout, and the menu-bar verdict matches control readiness."
