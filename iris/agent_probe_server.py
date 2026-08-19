"""Disposable stdio MCP server used only by :mod:`iris.agent_probe`."""
from __future__ import annotations

import json
import sys


TOOLS = [
    {"name": "iris_probe_read", "description": "Returns fixed probe metadata.", "inputSchema": {"type": "object"}},
    {"name": "iris_probe_write", "description": "Always denies a fake mutation.", "inputSchema": {"type": "object"}},
]


def _reply(identifier, result):
    sys.stdout.write(json.dumps({"jsonrpc": "2.0", "id": identifier, "result": result}) + "\n")
    sys.stdout.flush()


def main() -> int:
    for line in sys.stdin:
        try:
            request = json.loads(line)
            method, identifier = request.get("method"), request.get("id")
            if method == "initialize":
                _reply(identifier, {"protocolVersion": "2024-11-05", "capabilities": {"tools": {}},
                                    "serverInfo": {"name": "iris-probe", "version": "1"}})
            elif method == "tools/list":
                _reply(identifier, {"tools": TOOLS})
            elif method == "tools/call":
                name = request.get("params", {}).get("name")
                if name == "iris_probe_read":
                    _reply(identifier, {"content": [{"type": "text", "text": "read-only probe complete"}]})
                else:
                    _reply(identifier, {"content": [{"type": "text", "text": "mutation denied"}], "isError": True})
        except (TypeError, ValueError, json.JSONDecodeError):
            continue
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
