#!/usr/bin/env bash
#
# install-plugin.sh install|remove — put the Iris menu bar indicator in front of
# (or take it out of) SwiftBar. Called by scripts/install.sh and
# scripts/uninstall.sh so the daemon and its indicator travel together.
#
# The menu bar item is optional. If SwiftBar is not installed this exits 0 with
# a note: a missing indicator must never fail the daemon install.
#
# SWIFTBAR_PLUGIN_DIR overrides the destination. Production never sets it; the
# test suite does, which is how the round trip is verified without touching the
# real plugin directory.
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

# Only consult SwiftBar itself when the caller has not redirected us.
if [ -z "${SWIFTBAR_PLUGIN_DIR:-}" ] && [ ! -d "/Applications/SwiftBar.app" ]; then
  echo "SwiftBar not installed — skipping the menu bar indicator."
  echo "  brew install --cask swiftbar, then rerun ./scripts/install.sh"
  exit 0
fi

plugin_dir="$(resolve_plugin_dir)"

if [ "$action" = "remove" ]; then
  # Leave SwiftBar running: it may be hosting other plugins.
  rm -f "$plugin_dir/$plugin"
  echo "Removed the Iris menu bar indicator from $plugin_dir."
  exit 0
fi

[ "$action" = "install" ] || { echo "usage: $0 install|remove" >&2; exit 2; }

mkdir -p "$plugin_dir"
cp "$source_plugin" "$plugin_dir/$plugin"
chmod +x "$plugin_dir/$plugin"

if [ -z "${SWIFTBAR_PLUGIN_DIR:-}" ]; then
  # Claim the directory only when SwiftBar has none; never repoint an existing
  # one, which would orphan whatever plugins the user already runs.
  if [ -z "$(defaults read com.ameba.SwiftBar PluginDirectory 2>/dev/null || true)" ]; then
    defaults write com.ameba.SwiftBar PluginDirectory "$plugin_dir"
  fi
  # SwiftBar watches the plugin directory, so a running instance picks this up.
  open -ga SwiftBar 2>/dev/null || true
fi

echo "Menu bar indicator installed to $plugin_dir/$plugin."
