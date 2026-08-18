#!/usr/bin/env bash
set -euo pipefail

plist="$HOME/Library/LaunchAgents/com.iris.gateway.plist"
grep --quiet '<key>KeepAlive</key>' "$plist"
grep --quiet '<true/>' "$plist"
grep --quiet '<key>ThrottleInterval</key><integer>10</integer>' "$plist"
grep --quiet '<key>StandardOutPath</key>' "$plist"
