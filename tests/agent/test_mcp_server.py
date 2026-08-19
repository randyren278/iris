from iris.mcp_server import dispatch, tool_specs


def test_mcp_server_exposes_only_registered_read_tools_and_returns_structured_result():
    tools = {"weather": (lambda args: {"place": args["location"]},
                         {"location": {"type": "string"}}, ("location",))}
    spec = tool_specs(tools)[0]
    assert spec["name"] == "weather"
    assert spec["inputSchema"]["required"] == ["location"]
    result = dispatch(tools, "weather", {"location": "Boracay"})
    assert result.get("isError") is not True
    assert '"trust": "untrusted_data"' in result["content"][0]["text"]


def test_mcp_server_denies_unknown_or_malformed_tool_calls():
    assert dispatch({}, "write_file", {})["isError"] is True
    assert dispatch({"x": (lambda _args: None, {}, ())}, "x", "not-an-object")["isError"] is True
