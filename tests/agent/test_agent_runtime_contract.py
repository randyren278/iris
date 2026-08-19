import pytest

from iris.agent_runtime import AgentProtocolError, AgentReply, AgentRuntime
from iris.tool_protocol import ToolRequest


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


def test_malformed_or_non_terminating_agent_fails_closed():
    class BadAgent:
        def next_step(self, _text, _results): return object()

    with pytest.raises(AgentProtocolError, match="invalid message"):
        AgentRuntime({}).reply(BadAgent(), "hello")
