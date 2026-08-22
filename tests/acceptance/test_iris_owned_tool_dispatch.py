"""End-to-end proof that Iris, not the Claude CLI, runs a conversational tool.

The nested CLI is faked here (a real one would need network and credentials),
but everything on Iris's side of the boundary is production code: the real
catalog from iris.mcp_server, the real WorkspaceInspector, the real
AgentRuntime dispatch loop, the real coordinator, and the real Slack gateway.
"""
import json

from iris.agent_conversation import ClaudeToolAgentAdapter, GeneralAgentCoordinator
from iris.agent_runtime import AgentRuntime
from iris.slack import SlackGateway
from iris.tool_protocol import ToolRequest
from tests.gateway.test_slack_echo_e2e import dm_envelope
from tests.slack_fakes import RecordingSlackClient


class ScriptedClaude:
    """Stands in for the nested `claude -p` process, one reply per invocation."""

    def __init__(self, *replies):
        self.replies = list(replies)
        self.prompts = []

    def __call__(self, command, **_kwargs):
        self.prompts.append(command[-1])
        from types import SimpleNamespace
        return SimpleNamespace(returncode=0,
                               stdout=json.dumps({"result": self.replies.pop(0)}))


def build(tmp_path, claude, *, action_socket=None, thread_ts=None):
    def factory(message, turns, context):
        return ClaudeToolAgentAdapter(
            tmp_path, tmp_path / "senses.json", turns, context, run=claude,
            action_socket=action_socket, channel_id=message.channel_id,
            thread_ts=thread_ts or message.reply_thread_ts,
        )

    return GeneralAgentCoordinator(AgentRuntime({}), factory)


def test_dm_tool_request_is_executed_by_iris_and_answered_in_the_same_thread(tmp_path):
    (tmp_path / "NOTES.md").write_text("iris ships on friday")

    claude = ScriptedClaude(
        ToolRequest("r1", "workspace", {"path": "NOTES.md"}).to_json(),
        "Your notes say iris ships on friday.",
    )
    conversation = build(tmp_path, claude)
    client = RecordingSlackClient()
    accepted = SlackGateway(["U-allowed"], client, handler=conversation.reply).handle_envelope(
        dm_envelope(text="what do my notes say?", ts="10.2", thread_ts="10.1"))

    assert accepted is True
    assert client.messages == [{
        "channel_id": "D-1", "thread_ts": "10.1",
        "text": "Your notes say iris ships on friday.",
    }]
    # The second planning turn must have seen the real file contents, which is
    # only possible if Iris actually ran WorkspaceInspector in-process.
    assert "iris ships on friday" in claude.prompts[1]
    assert "iris ships on friday" not in claude.prompts[0]


def test_the_nested_process_is_never_given_tools_or_operator_settings(tmp_path):
    commands = []

    def claude(command, **_kwargs):
        from types import SimpleNamespace
        commands.append(command)
        return SimpleNamespace(returncode=0, stdout=json.dumps({"result": "nothing to do"}))

    build(tmp_path, claude).reply(
        type("M", (), {"text": "hi", "channel_id": "D-1", "reply_thread_ts": "1.0"})())

    built = commands[0]
    assert built[built.index("--tools") + 1] == ""
    assert built[built.index("--setting-sources") + 1] == ""
    assert "--mcp-config" not in built
    assert "--allowedTools" not in built


def test_a_tool_iris_does_not_publish_is_refused_and_reported_back(tmp_path):
    claude = ScriptedClaude(
        ToolRequest("r1", "shell", {"command": "rm -rf /"}).to_json(),
        "I can't do that.",
    )
    conversation = build(tmp_path, claude)
    client = RecordingSlackClient()
    SlackGateway(["U-allowed"], client, handler=conversation.reply).handle_envelope(
        dm_envelope(text="delete everything", ts="10.2", thread_ts="10.1"))

    assert client.messages[0]["text"] == "I can't do that."
    assert "tool is not available" in claude.prompts[1]


def test_workspace_escape_is_rejected_by_iris_not_answered(tmp_path):
    claude = ScriptedClaude(
        ToolRequest("r1", "workspace", {"path": "../../etc/passwd"}).to_json(),
        "That path is outside my workspace.",
    )
    conversation = build(tmp_path, claude)
    client = RecordingSlackClient()
    SlackGateway(["U-allowed"], client, handler=conversation.reply).handle_envelope(
        dm_envelope(text="read /etc/passwd", ts="10.2", thread_ts="10.1"))

    assert client.messages[0]["text"] == "That path is outside my workspace."
    assert "tool request was rejected" in claude.prompts[1]
    assert "root:" not in claude.prompts[1]


def test_start_coding_is_absent_without_a_slack_origin_even_if_the_model_asks(tmp_path):
    claude = ScriptedClaude(
        ToolRequest("r1", "start_coding",
                    {"tool": "claude", "project": "x", "task": "y"}).to_json(),
        "I can't start that.",
    )
    # An action socket but no thread origin: the approval-bound tool must not
    # be dispatchable, so the request comes back unavailable.
    conversation = build(tmp_path, claude, action_socket=tmp_path / "a.sock", thread_ts=None)
    client = RecordingSlackClient()

    class Message:
        text, channel_id, reply_thread_ts = "build me a thing", "D-1", None

    conversation.reply(Message())
    assert "tool is not available" in claude.prompts[1]
