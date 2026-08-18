#!/usr/bin/env bash
set -euo pipefail

codex --version >/dev/null
codex exec --help | grep --quiet -- '--sandbox'
