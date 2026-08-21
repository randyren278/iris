#!/usr/bin/env bash
#
# install-plugin.sh install|remove — put the Iris menu-bar control plane in
# front of SwiftBar (or take it out). Called by scripts/install.sh and
# scripts/uninstall.sh so the daemon and its observable control plane travel
# together.
#
# A production `install` requires SwiftBar. Iris must not claim a complete
# install while its primary local health/armed-state indicator is absent.
# `remove` remains safe even if SwiftBar itself is already gone.
#
# SWIFTBAR_PLUGIN_DIR overrides the destination. Production never sets it; the
# test suite does, which is how the round trip is verified without touching the
# real plugin directory or requiring macOS.
set -euo pipefail

action="${1:-install}"
plugin="iris.30s.sh"
source_plugin="$(cd "$(dirname "$0")" && pwd)/$plugin"

resolve_plugin_dir() {
  if [ -n "${SWIFTBAR_PLUGIN_DIR:-}" ]; then
    echo "$SWIFTBAR_PLUGIN_DIR"
    return
  fi
  local configured
  configured="$(defaults read com.ameba.SwiftBar PluginDirectory 2>/dev/null || true)"
  echo "${configured:-$HOME/.swiftbar-plugins}"
}

[ "$action" = "install" ] || [ "$action" = "remove" ] || {
  echo "usage: $0 install|remove" >&2
  exit 2
}

plugin_dir="$(resolve_plugin_dir)"

if [ "$action" = "remove" ]; then
  # Leave SwiftBar running: it may be hosting other plugins.
  rm -f "$plugin_dir/$plugin"
  echo "Removed the Iris menu bar control plane from $plugin_dir."
  exit 0
fi

# Test callers deliberately redirect the destination and therefore do not need
# the GUI application. Production has no override and must have SwiftBar.
if [ -z "${SWIFTBAR_PLUGIN_DIR:-}" ] && [ ! -d "/Applications/SwiftBar.app" ]; then
  echo "SwiftBar is required for the Iris production control plane." >&2
  echo "Install it with: brew install --cask swiftbar" >&2
  echo "Then rerun: ./scripts/install.sh" >&2
  exit 1
fi

mkdir -p "$plugin_dir"
cp "$source_plugin" "$plugin_dir/$plugin"
chmod +x "$plugin_dir/$plugin"

if [ -z "${SWIFTBAR_PLUGIN_DIR:-}" ]; then
  # Claim the directory only when SwiftBar has none; never repoint an existing
  # one, which would orphan whatever plugins the user already runs.
  if [ -z "$(defaults read com.ameba.SwiftBar PluginDirectory 2>/dev/null || true)" ]; then
    defaults write com.ameba.SwiftBar PluginDirectory "$plugin_dir"
  fi

  open -ga SwiftBar >/dev/null 2>&1 || {
    echo "SwiftBar is installed but could not be launched." >&2
    exit 1
  }
  running=false
  for _attempt in 1 2 3 4 5 6 7 8 9 10; do
    if pgrep -x SwiftBar >/dev/null 2>&1; then
      running=true
      break
    fi
    sleep 0.5
  done
  if [ "$running" != true ]; then
    echo "SwiftBar did not stay running after launch; Iris control-plane install is incomplete." >&2
    exit 1
  fi
fi

echo "Menu bar control plane installed to $plugin_dir/$plugin."
