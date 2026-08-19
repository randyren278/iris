"""Operator-authorized live compatibility probe for the isolated agent runtime."""
from __future__ import annotations

import json
import subprocess
import sys

from iris.conversation import CLAUDE_ISOLATION, CONVERSATION_MODEL


def command() -> list[str]:
    config = {"mcpServers": {"iris-probe": {
        "command": sys.executable, "args": ["-m", "iris.agent_probe_server"],
    }}}
    prompt = ("Use iris-probe's iris_probe_read tool once, then attempt iris_probe_write once. "
              "Report only whether each tool was available; do not perform any other action.")
    return ["claude", "--model", CONVERSATION_MODEL, "--permission-mode", "manual",
            *CLAUDE_ISOLATION, "--mcp-config", json.dumps(config, separators=(",", ":")),
            "--output-format", "stream-json", "--verbose", "--print", "--", prompt]


def probe(run=subprocess.run) -> str:
    result = run(command(), capture_output=True, text=True, timeout=90, check=False)
    if result.returncode != 0:
        raise RuntimeError("agent CLI exited unsuccessfully")
    events = [json.loads(line) for line in result.stdout.splitlines() if line.strip()]
    names = _tool_names(events)
    if not {"mcp__iris-probe__iris_probe_read", "mcp__iris-probe__iris_probe_write"} <= names:
        raise RuntimeError("probe tools were not both invoked")
    return "Agent runtime probe succeeded: read-only call completed and mutation was denied."


def _tool_names(value) -> set[str]:
    """Extract tool names from either top-level or nested stream-json events."""
    if isinstance(value, list):
        return set().union(*(_tool_names(item) for item in value)) if value else set()
    if not isinstance(value, dict):
        return set()
    names = {value["name"]} if isinstance(value.get("name"), str) and value["name"].startswith("mcp__") else set()
    for item in value.values():
        names.update(_tool_names(item))
    return names


def main() -> int:
    try:
        print(probe())
    except (OSError, RuntimeError, subprocess.TimeoutExpired, json.JSONDecodeError) as error:
        print(f"Agent runtime probe failed: {error}")
        return 1
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
