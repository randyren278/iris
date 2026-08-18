#!/bin/bash
# Thin wrapper around the real fail-closed-path checks; sockets and raw
# byte-level protocol violations are easier to construct in Python.
set -eu
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$REPO_ROOT"
exec .venv/bin/python scripts/checks/live_deny_paths.py
