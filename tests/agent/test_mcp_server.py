from iris.mcp_server import dispatch, tool_specs


def test_mcp_server_exposes_only_registered_read_tools_and_returns_structured_result():
    tools = {"weather": (lambda args: {"place": args["location"]}, {"location": {"type": "string"}})}
    assert tool_specs(tools)[0]["name"] == "weather"
    assert dispatch(tools, "weather", {"location": "Boracay"}).get("isError") is not True


def test_mcp_server_denies_unknown_or_malformed_tool_calls():
    assert dispatch({}, "write_file", {})["isError"] is True
    assert dispatch({"x": (lambda _args: None, {})}, "x", "not-an-object")["isError"] is True
