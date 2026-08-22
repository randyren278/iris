import json
from types import SimpleNamespace

from iris.agent_actions import request_action
from iris.agent_probe import _tool_names, action_probe, command, probe
from iris.agent_runtime import AgentReply
from iris.tool_protocol import ToolRequest


def test_probe_command_uses_only_isolated_disposable_mcp_configuration():
    built = command()
    assert "--setting-sources" in built and "--strict-mcp-config" in built
    config = json.loads(built[built.index("--mcp-config") + 1])
    assert config["mcpServers"]["iris-probe"]["args"] == ["-m", "iris.agent_probe_server"]


def test_probe_requires_both_fake_tool_events_without_printing_payloads():
    output = "\n".join(json.dumps({"type": "tool_use", "name": name}) for name in (
        "mcp__iris-probe__iris_probe_read", "mcp__iris-probe__iris_probe_write"))
    result = probe(lambda *_args, **_kwargs: SimpleNamespace(returncode=0, stdout=output))
    assert result == "Agent runtime probe succeeded: read-only call completed and mutation was denied."


def test_probe_finds_tool_events_nested_in_stream_messages():
    assert _tool_names({"message": {"content": [{"type": "tool_use", "name": "mcp__iris-probe__iris_probe_read"}]}}) == {
        "mcp__iris-probe__iris_probe_read"
    }


def test_action_probe_exercises_action_socket_without_real_coding_process():
    class FakeActionAdapter:
        def __init__(self, _root, _senses, _turns, _context, *, action_socket,
                     channel_id, thread_ts, **_kwargs):
            self.action_socket = action_socket
            self.channel_id = channel_id
            self.thread_ts = thread_ts

        def handlers(self):
            # Mirrors production: the adapter publishes the tool, and only
            # AgentRuntime runs it.
            return {"start_coding": lambda arguments: request_action(
                self.action_socket, "start_coding", arguments,
                channel_id=self.channel_id, thread_ts=self.thread_ts,
            )}

        def next_step(self, _prompt, results):
            if not results:
                return ToolRequest("probe-1", "start_coding", {
                    "tool": "claude", "project": "IrisProbe", "task": "probe only"})
            return AgentReply("started")

    assert action_probe(FakeActionAdapter) == (
        "Agent action probe succeeded: Claude crossed Iris's tool runtime into one approved daemon action."
    )
