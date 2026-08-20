"""Claude hook entry point: ask Iris locally and deny on every failure."""
from __future__ import annotations

import json
import os
import sys

from iris.approvals import request_approval

MAX_SUMMARY_CHARS = 1600


def summarize_tool_call(payload: dict) -> str:
    """Render the exact requested tool and bounded arguments for human review."""
    name = payload.get("tool_name")
    tool_name = name if isinstance(name, str) and name else "tool call"
    tool_input = payload.get("tool_input")
    if not isinstance(tool_input, dict) or not tool_input:
        return tool_name
    rendered = json.dumps(tool_input, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    if len(rendered) > MAX_SUMMARY_CHARS:
        rendered = rendered[:MAX_SUMMARY_CHARS - 3] + "..."
    return f"{tool_name} {rendered}"


def main() -> int:
    try:
        payload = json.load(sys.stdin)
        if not isinstance(payload, dict):
            raise ValueError("hook payload must be an object")
        summary = summarize_tool_call(payload)
        socket_path = os.environ["IRIS_APPROVAL_SOCKET"]
        channel_id = os.environ.get("IRIS_APPROVAL_CHANNEL_ID")
        thread_ts = os.environ.get("IRIS_APPROVAL_THREAD_TS")
        approved = request_approval(
            socket_path,
            summary,
            channel_id=channel_id,
            thread_ts=thread_ts,
        )
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
