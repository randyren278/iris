#!/bin/bash
# Thin wrapper: orchestrating threads/sockets/a real claude subprocess is
# easier in Python. This is the entry point checks and CI-equivalents should
# reference.
set -eu
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$REPO_ROOT"
exec .venv/bin/python scripts/checks/live_approval.py
