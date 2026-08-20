import pytest

from iris.agent_runtime import AgentProtocolError, AgentReply, AgentRuntime
from iris.tool_protocol import ProtocolError, ToolRequest


class TwoStepAgent:
    def next_step(self, _user_text, results):
        if not results:
            return ToolRequest("one", "first", {"query": "alpha"})
        if len(results) == 1:
            assert results[0].content == {"value": "A"}
            return ToolRequest("two", "second", {"value": "A"})
        assert results[1].content == {"value": "B"}
        return AgentReply("A then B")


def test_runtime_dispatches_multiple_structured_tool_results_without_exposing_handles():
    calls = []
    runtime = AgentRuntime({
        "first": lambda args: calls.append(("first", args)) or {"value": "A"},
        "second": lambda args: calls.append(("second", args)) or {"value": "B"},
    })
    assert runtime.reply(TwoStepAgent(), "compare them") == "A then B"
    assert calls == [("first", {"query": "alpha"}), ("second", {"value": "A"})]


def test_unknown_and_mutating_tools_are_not_dispatchable_without_a_registered_handle():
    calls = []

    class Agent:
        def next_step(self, _text, results):
            if not results:
                return ToolRequest("write", "write_file", {"path": "x"})
            assert results[0].error == "tool is not available"
            return AgentReply("I could not do that")

    assert AgentRuntime({"read_file": lambda args: calls.append(args)}).reply(Agent(), "write x") == "I could not do that"
    assert calls == []


def test_user_text_and_agent_reply_must_be_nonempty_strings():
    class EmptyReply:
        def next_step(self, _text, _results):
            return AgentReply("")

    for text in ("", None, 3):
        with pytest.raises(AgentProtocolError, match="user text is required"):
            AgentRuntime({}).reply(EmptyReply(), text)
    with pytest.raises(AgentProtocolError, match="agent reply is empty"):
        AgentRuntime({}).reply(EmptyReply(), "hello")


def test_malformed_agent_message_fails_closed():
    class BadAgent:
        def next_step(self, _text, _results):
            return object()

    with pytest.raises(AgentProtocolError, match="invalid message"):
        AgentRuntime({}).reply(BadAgent(), "hello")


def test_reused_request_id_is_rejected_before_second_dispatch():
    calls = []

    class Reuser:
        def next_step(self, _text, results):
            if not results:
                return ToolRequest("same", "read", {"n": 1})
            return ToolRequest("same", "read", {"n": 2})

    with pytest.raises(AgentProtocolError, match="reused a tool request id"):
        AgentRuntime({"read": lambda args: calls.append(args) or args}).reply(Reuser(), "go")
    assert calls == [{"n": 1}]


def test_nonterminating_agent_hits_configured_step_limit():
    class Loop:
        def __init__(self):
            self.count = 0

        def next_step(self, _text, _results):
            self.count += 1
            return ToolRequest(str(self.count), "read", {})

    agent = Loop()
    with pytest.raises(AgentProtocolError, match="exceeded the tool-step limit"):
        AgentRuntime({"read": lambda _args: "ok"}, max_steps=2).reply(agent, "go")
    assert agent.count == 2


@pytest.mark.parametrize("error", [ProtocolError("bad protocol"), ValueError("bad value"), TypeError("bad type")])
def test_validation_like_handler_failures_become_rejected_results(error):
    class Agent:
        def next_step(self, _text, results):
            if not results:
                return ToolRequest("1", "read", {})
            assert results[0].error == "tool request was rejected"
            return AgentReply("rejected safely")

    def handler(_args):
        raise error

    assert AgentRuntime({"read": handler}).reply(Agent(), "go") == "rejected safely"


def test_unexpected_handler_failure_is_hidden_from_agent():
    class Agent:
        def next_step(self, _text, results):
            if not results:
                return ToolRequest("1", "read", {})
            assert results[0].error == "tool is unavailable"
            assert "secret" not in results[0].error
            return AgentReply("unavailable safely")

    def handler(_args):
        raise RuntimeError("secret backend detail")

    assert AgentRuntime({"read": handler}).reply(Agent(), "go") == "unavailable safely"
