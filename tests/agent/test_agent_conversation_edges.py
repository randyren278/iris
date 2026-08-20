import json
import subprocess
from types import SimpleNamespace

from iris.agent_conversation import ClaudeMCPAgentAdapter, GeneralAgentCoordinator
from iris.agent_runtime import AgentReply
from iris.conversation import MemoryContext


def test_adapter_returns_safe_unavailable_reply_on_oserror_and_timeout(tmp_path):
    for error in (OSError("missing"), subprocess.TimeoutExpired("claude", 1)):
        def run(*_args, **_kwargs):
            raise error
        adapter = ClaudeMCPAgentAdapter(tmp_path, tmp_path / "senses.json", (), (), run=run)
        reply = adapter.next_step("hello", ())
        assert "temporarily unavailable" in reply.text
        assert "missing" not in reply.text


def test_adapter_returns_safe_failure_on_nonzero_process(tmp_path):
    adapter = ClaudeMCPAgentAdapter(
        tmp_path, tmp_path / "senses.json", (), (),
        run=lambda *_a, **_k: SimpleNamespace(returncode=7, stdout="secret", stderr="private"),
    )
    assert adapter.next_step("hello", ()).text == "I couldn't complete that agent turn. Please try again."


def test_adapter_accepts_plain_stdout_when_cli_output_is_not_json(tmp_path):
    adapter = ClaudeMCPAgentAdapter(
        tmp_path, tmp_path / "senses.json", (), (),
        run=lambda *_a, **_k: SimpleNamespace(returncode=0, stdout=" plain response \n"),
    )
    assert adapter.next_step("hello", ()).text == "plain response"


def test_adapter_uses_empty_fallback_for_empty_or_missing_json_result(tmp_path):
    for stdout in ('{"result":"   "}', '{}'):
        adapter = ClaudeMCPAgentAdapter(
            tmp_path, tmp_path / "senses.json", (), (),
            run=lambda *_a, _stdout=stdout, **_k: SimpleNamespace(returncode=0, stdout=_stdout),
        )
        assert adapter.next_step("hello", ()).text == "I don't have a response for that yet."


def test_adapter_command_has_no_action_args_for_partial_origin(tmp_path):
    adapter = ClaudeMCPAgentAdapter(
        tmp_path, tmp_path / "senses.json", (), (),
        action_socket=tmp_path / "action.sock", channel_id="D1",
    )
    command = adapter.command()
    config = json.loads(command[command.index("--mcp-config") + 1])
    args = config["mcpServers"]["iris"]["args"]
    assert "--action-socket" not in args
    assert "--channel-id" not in args
    assert "--thread-ts" not in args


class RecordingRuntime:
    def __init__(self):
        self.calls = []

    def reply(self, agent, text):
        self.calls.append((agent, text))
        return agent.next_step(text, ()).text


def message(text, *, channel="D1", thread="1.0"):
    return SimpleNamespace(text=text, channel_id=channel, reply_thread_ts=thread)


def test_coordinator_filters_untrusted_context_and_passes_thread_turns():
    runtime = RecordingRuntime()
    factory_calls = []

    def context_provider(key, text):
        assert key == ("D1", "1.0")
        assert text == "hello"
        return (
            MemoryContext("keep self", "self", "self-source"),
            MemoryContext("keep team", "team", "team-source"),
            MemoryContext("drop web", "untrusted", "web"),
        )

    class Agent:
        def next_step(self, _text, _results):
            return AgentReply("reply")

    def factory(msg, turns, context):
        factory_calls.append((msg, turns, context))
        return Agent()

    coordinator = GeneralAgentCoordinator(runtime, factory, context_provider=context_provider)
    assert coordinator.reply(message("hello")) == "reply"
    _msg, turns, context = factory_calls[0]
    assert [(turn.role, turn.text) for turn in turns] == [("user", "hello")]
    assert [item.text for item in context] == ["keep self", "keep team"]


def test_coordinator_supports_legacy_one_argument_context_provider():
    runtime = RecordingRuntime()
    seen = []

    def legacy(key):
        seen.append(key)
        return ()

    class Agent:
        def next_step(self, _text, _results):
            return AgentReply("ok")

    coordinator = GeneralAgentCoordinator(runtime, lambda *_args: Agent(), context_provider=legacy)
    assert coordinator.reply(message("hello", thread="2.0")) == "ok"
    assert seen == [("D1", "2.0")]


def test_coordinator_keeps_short_term_history_per_thread_and_trims_to_bound():
    runtime = RecordingRuntime()
    snapshots = []

    class Agent:
        def __init__(self, reply):
            self.reply = reply

        def next_step(self, _text, _results):
            return AgentReply(self.reply)

    def factory(msg, turns, _context):
        snapshots.append((msg.reply_thread_ts, [(turn.role, turn.text) for turn in turns]))
        return Agent(f"answer-{msg.text}")

    coordinator = GeneralAgentCoordinator(runtime, factory, max_messages=4)
    assert coordinator.reply(message("one", thread="A")) == "answer-one"
    assert coordinator.reply(message("two", thread="A")) == "answer-two"
    assert coordinator.reply(message("three", thread="A")) == "answer-three"
    assert coordinator.reply(message("separate", thread="B")) == "answer-separate"

    # Before answering a turn, the bounded stored history is visible together
    # with the just-appended current user message. After the response, storage
    # trims back to max_messages for the following turn.
    assert snapshots[2][1] == [
        ("user", "one"), ("assistant", "answer-one"),
        ("user", "two"), ("assistant", "answer-two"),
        ("user", "three"),
    ]
    coordinator.reply(message("four", thread="A"))
    assert snapshots[-1][1] == [
        ("user", "two"),
        ("assistant", "answer-two"),
        ("user", "three"),
        ("assistant", "answer-three"),
        ("user", "four"),
    ]
    assert snapshots[3] == ("B", [("user", "separate")])
