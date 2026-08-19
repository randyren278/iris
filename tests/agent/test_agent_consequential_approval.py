from iris.agent_capabilities import AgentApprovalGate, AgentCapabilityExecutor
from iris.tool_catalog import ToolCatalog, ToolDefinition, ToolMode
from iris.tool_protocol import ToolRequest


def _valid(arguments): return arguments


def test_consequential_call_runs_only_after_exact_approval_and_is_thread_bound():
    notices, writes = [], []
    gate = AgentApprovalGate(lambda summary, _timeout: notices.append(summary) or True,
                             nonce_factory=lambda _size: "nonce")
    catalog = ToolCatalog((ToolDefinition("write_file", ToolMode.CONSEQUENTIAL, _valid,
                                          lambda args: writes.append(args) or {"ok": True}, "local", 2),))
    result = AgentCapabilityExecutor(catalog, gate).invoke(
        ToolRequest("request", "write_file", {"path": "x", "body": "hello"}), channel_id="D1", thread_ts="T1")
    assert result.content == {"ok": True}
    assert writes == [{"path": "x", "body": "hello"}]
    assert '"body": "hello"' in notices[0] and "D1/T1" in notices[0]


def test_denial_or_missing_approval_service_never_runs_the_handler():
    calls = []
    catalog = ToolCatalog((ToolDefinition("write", ToolMode.CONSEQUENTIAL, _valid,
                                          lambda args: calls.append(args), "local", 2),))
    executor = AgentCapabilityExecutor(catalog, AgentApprovalGate(lambda *_args: (_ for _ in ()).throw(OSError())))
    result = executor.invoke(ToolRequest("r", "write", {"path": "x"}), channel_id="D", thread_ts="T")
    assert result.error == "tool request was denied"
    assert calls == []


def test_queue_adapter_uses_the_origin_thread_notifier_for_this_approval():
    class Queue:
        def request(self, summary, *, timeout, notifier):
            notifier(summary)
            assert timeout == 3
            return True
    notices = []
    gate = AgentApprovalGate.from_queue(Queue(), notices.append, nonce_factory=lambda _size: "nonce")
    assert gate.request(gate.bind("write", {"path": "x"}, "D", "T"), timeout=3) is True
    assert "D/T" in notices[0]
