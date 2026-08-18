"""Claude hook entry point: ask Iris locally and deny on every failure."""
from __future__ import annotations

import json
import os
import sys

from iris.approvals import request_approval


def main() -> int:
    try:
        payload = json.load(sys.stdin)
        summary = payload.get("tool_name", "tool call")
        socket_path = os.environ["IRIS_APPROVAL_SOCKET"]
        approved = request_approval(socket_path, str(summary))
    except (OSError, ValueError, json.JSONDecodeError, KeyError, TypeError, AttributeError):
        approved = False
    # PreToolUse hooks require the event-specific nested schema. A plain
    # top-level decision is ignored by current Claude Code releases.
    json.dump({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "allow" if approved else "deny",
            "permissionDecisionReason": "Approved by Iris" if approved else "Denied by Iris",
        }
    }, sys.stdout)
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI wrapper
    raise SystemExit(main())
