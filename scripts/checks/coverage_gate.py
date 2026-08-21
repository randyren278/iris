#!/usr/bin/env python3
"""Hold every production-critical module to its own branch-coverage floor.

The repo-wide `fail_under` in pyproject.toml is an average: a thoroughly
covered leaf module can hide a weakly covered control-plane one, and the
control plane is exactly where an untested branch becomes an authority bug.
This gate re-checks the modules that carry the daemon, the Slack gateway, the
approval path and the bounded tools individually.

A module named here that is absent from the coverage report is a failure, not
a skip -- otherwise renaming or deleting a module silently retires its floor.

Usage:
    coverage_gate.py --coverage-json coverage.json [--floor 95.0]
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys

# The Slack intent -> bounded reasoning -> validated request -> approval ->
# daemon-controlled execution path, plus the tools a conversational turn can
# actually reach.
PRODUCTION_CRITICAL = (
    "iris/agent_actions.py",
    "iris/agent_conversation.py",
    "iris/agent_runtime.py",
    "iris/approvals.py",
    "iris/config.py",
    "iris/irisctl.py",
    "iris/launcher.py",
    "iris/main.py",
    "iris/mcp_server.py",
    "iris/memory.py",
    "iris/router.py",
    "iris/runtime.py",
    "iris/session_transport.py",
    "iris/sessions.py",
    "iris/slack.py",
    "iris/tool_protocol.py",
    "iris/tools/senses.py",
    "iris/tools/web.py",
    "iris/tools/workspace.py",
)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--coverage-json", type=pathlib.Path, required=True)
    parser.add_argument("--floor", type=float, default=95.0)
    args = parser.parse_args(argv)

    try:
        report = json.loads(args.coverage_json.read_text())
    except (OSError, json.JSONDecodeError) as error:
        print(f"FAIL: cannot read {args.coverage_json}: {error}", file=sys.stderr)
        return 1

    files = report.get("files", {})
    missing: list[str] = []
    below: list[tuple[str, float]] = []
    for module in PRODUCTION_CRITICAL:
        entry = files.get(module)
        if entry is None:
            missing.append(module)
            continue
        percent = entry["summary"]["percent_covered"]
        if percent < args.floor:
            below.append((module, percent))
        print(f"{percent:6.1f}%  {module}")

    if missing:
        print(f"\nFAIL: {len(missing)} production-critical module(s) absent from the "
              f"coverage report -- update PRODUCTION_CRITICAL if this was a rename, "
              f"do not let the floor lapse:", file=sys.stderr)
        for module in missing:
            print(f"  {module}", file=sys.stderr)
        return 1

    if below:
        print(f"\nFAIL: {len(below)} production-critical module(s) below "
              f"{args.floor:.1f}% branch coverage:", file=sys.stderr)
        for module, percent in below:
            print(f"  {percent:6.1f}%  {module}", file=sys.stderr)
        return 1

    print(f"\nPASS: {len(PRODUCTION_CRITICAL)} production-critical modules "
          f"at or above {args.floor:.1f}%")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
