#!/usr/bin/env bash
set -euo pipefail

label="com.iris.gateway"
domain="gui/$(id -u)"
target="$HOME/Library/LaunchAgents/$label.plist"
launchctl bootout "$domain/$label" 2>/dev/null || launchctl bootout "$domain" "$target" 2>/dev/null || true
rm -f "$target"
