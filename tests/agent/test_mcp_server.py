from iris.agent_actions import AgentActionError
from iris.mcp_server import catalog, dispatch, tool_specs


def test_mcp_server_exposes_only_registered_read_tools_and_returns_structured_result():
    tools = {"weather": (lambda args: {"place": args["location"]},
                         {"location": {"type": "string"}}, ("location",))}
    spec = tool_specs(tools)[0]
    assert spec["name"] == "weather"
    assert spec["inputSchema"]["required"] == ["location"]
    result = dispatch(tools, "weather", {"location": "Boracay"})
    assert result.get("isError") is not True
    assert '"trust": "untrusted_data"' in result["content"][0]["text"]


def test_consequential_action_is_exposed_only_with_socket_and_exact_origin(tmp_path):
    senses = tmp_path / "senses.json"
    assert "start_coding" not in catalog(tmp_path, senses)
    assert "start_coding" not in catalog(
        tmp_path, senses, action_socket=tmp_path / "action.sock", channel_id="D-1")

    tools = catalog(
        tmp_path,
        senses,
        action_socket=tmp_path / "action.sock",
        channel_id="D-1",
        thread_ts="10.2",
    )
    assert "start_coding" in tools
    spec = next(item for item in tool_specs(tools) if item["name"] == "start_coding")
    assert spec["inputSchema"]["required"] == ["tool", "project", "task"]
    assert "Approval-bound consequential action" in spec["description"]


def test_agent_action_denial_is_an_mcp_error_not_a_success():
    def denied(_args):
        raise AgentActionError("operator denied the action")

    result = dispatch({"start_coding": (denied, {}, ())}, "start_coding", {})
    assert result["isError"] is True
    assert "operator denied the action" in result["content"][0]["text"]


def test_mcp_server_denies_unknown_or_malformed_tool_calls():
    assert dispatch({}, "write_file", {})["isError"] is True
    assert dispatch({"x": (lambda _args: None, {}, ())}, "x", "not-an-object")["isError"] is True
