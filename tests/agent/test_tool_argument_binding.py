from iris.agent_capabilities import AgentApprovalGate, AgentCapabilityExecutor
from iris.tool_catalog import ToolCatalog, ToolDefinition, ToolMode
from iris.tool_protocol import ToolRequest


def test_mutating_original_arguments_after_binding_cannot_substitute_approved_call():
    approved, writes = [], []
    source = {"path": "safe"}
    gate = AgentApprovalGate(lambda summary, _timeout: approved.append(summary) or True,
                             nonce_factory=lambda _size: "once")
    catalog = ToolCatalog((ToolDefinition("write", ToolMode.CONSEQUENTIAL, lambda args: args,
                                          lambda args: writes.append(args) or "done", "local", 2),))
    result = AgentCapabilityExecutor(catalog, gate).invoke(ToolRequest("r", "write", source), channel_id="D", thread_ts="T")
    source["path"] = "substituted"
    assert result.content == "done"
    assert writes == [{"path": "safe"}]


def test_approval_nonce_cannot_be_replayed():
    gate = AgentApprovalGate(lambda *_args: True, nonce_factory=lambda _size: "once")
    call = gate.bind("write", {"path": "x"}, "D", "T")
    assert gate.request(call, timeout=1) is True
    assert gate.request(call, timeout=1) is False
