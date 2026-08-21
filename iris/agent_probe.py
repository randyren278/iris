"""Operator-authorized live compatibility probes for Iris's agent runtime."""
from __future__ import annotations

import json
import pathlib
import subprocess
import sys
import tempfile
from types import SimpleNamespace

from iris import agent_probe_server
from iris.agent_actions import AgentActionServer
from iris.agent_conversation import ClaudeMCPAgentAdapter
from iris.approvals import ApprovalQueue
from iris.conversation import CLAUDE_ISOLATION, CONVERSATION_MODEL, ConversationMessage
from iris.projects import ProjectCatalog


def command() -> list[str]:
    config = {"mcpServers": {"iris-probe": {
        "command": sys.executable, "args": ["-m", agent_probe_server.__name__],
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


class _ProbeSessions:
    def __init__(self):
        self.calls = []

    def launch(self, tool, **kwargs):
        self.calls.append((tool, kwargs))
        return SimpleNamespace(id=1, tool=tool, cwd=str(kwargs["cwd"]))


def action_probe(adapter_factory=ClaudeMCPAgentAdapter) -> str:
    """Use the real Claude/MCP path but a fake session launcher and auto-approval."""
    with tempfile.TemporaryDirectory(prefix="iris-agent-action-probe-", dir="/tmp") as raw_root:
        root = pathlib.Path(raw_root)
        project = root / "IrisProbe"
        project.mkdir()
        queue = ApprovalQueue(notifier=lambda _text: None)
        sessions = _ProbeSessions()

        def notifier_for_context(channel_id, thread_ts):
            def approve(_text):
                if not queue.resolve(True, origin=(channel_id, thread_ts)):
                    raise RuntimeError("probe approval was not pending in the expected origin")
            return approve

        server = AgentActionServer(
            root / "action.sock",
            queue,
            ProjectCatalog.discover(root),
            sessions,
            notifier_for_context=notifier_for_context,
            timeout=10,
        )
        server.start()
        prompt = (
            "Use the Iris start_coding tool exactly once with tool=claude, project=IrisProbe, "
            "and task='probe only'. Do not use any other tool. After it returns, report the status."
        )
        try:
            adapter = adapter_factory(
                root,
                root / "senses.json",
                (ConversationMessage("user", prompt),),
                (),
                action_socket=server.path,
                channel_id="D-probe",
                thread_ts="1.0",
            )
            adapter.next_step(prompt, ())
        finally:
            server.close()
        if len(sessions.calls) != 1:
            raise RuntimeError("general agent did not invoke exactly one approved start_coding action")
        tool, kwargs = sessions.calls[0]
        if tool != "claude" or pathlib.Path(kwargs["cwd"]) != project.resolve() or kwargs["prompt"] != "probe only":
            raise RuntimeError("general agent action arguments did not survive validation unchanged")
    return "Agent action probe succeeded: Claude crossed MCP into one approved daemon action."


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
        print(action_probe())
    except (OSError, RuntimeError, subprocess.TimeoutExpired, json.JSONDecodeError) as error:
        print(f"Agent runtime probe failed: {error}")
        return 1
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
