#!/usr/bin/env bash
set -euo pipefail

claude --version >/dev/null
claude --help | grep --quiet -- '--permission-mode'
claude --help | grep --quiet -- '--remote-control'
