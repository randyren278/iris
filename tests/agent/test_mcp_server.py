import io
import json
import sys
from types import SimpleNamespace

import pytest

import iris.mcp_server as mcp
from iris.agent_actions import AgentActionError
from iris.mcp_server import catalog, dispatch, tool_specs, validate_weather_arguments


def test_mcp_server_exposes_only_registered_read_tools_and_returns_structured_result():
    tools = {"weather": (lambda args: {"place": args["location"]},
                         {"location": {"type": "string"}}, ("location",))}
    spec = tool_specs(tools)[0]
    assert spec["name"] == "weather"
    assert spec["inputSchema"]["required"] == ["location"]
    result = dispatch(tools, "weather", {"location": "Boracay"})
    assert result.get("isError") is not True
    assert '"trust": "untrusted_data"' in result["content"][0]["text"]


def test_catalog_builds_read_tools_senses_and_bound_action(tmp_path, monkeypatch):
    calls = []

    class Weather:
        def __call__(self, request):
            calls.append(("weather", request.arguments))
            return SimpleNamespace(text="sunny", source="fake", observed_at="now")

    class Web:
        def search(self, args):
            calls.append(("search", args))
            return {"search": args}

        def fetch(self, args):
            calls.append(("fetch", args))
            return {"fetch": args}

    class Workspace:
        def __init__(self, root):
            assert root == tmp_path

        def __call__(self, args):
            calls.append(("workspace", args))
            return {"workspace": args}

    monkeypatch.setattr(mcp, "WeatherService", Weather)
    monkeypatch.setattr(mcp, "WebFetcher", Web)
    monkeypatch.setattr(mcp, "WorkspaceInspector", Workspace)
    monkeypatch.setattr(mcp, "validate_search_arguments", lambda args: {"query": args["query"].strip()})
    monkeypatch.setattr(mcp, "validate_fetch_arguments", lambda args: {"url": args["url"]})
    monkeypatch.setattr(mcp, "validate_workspace_arguments", lambda args: {"path": args["path"]})

    senses = tmp_path / "senses.json"
    senses.write_text("[]")
    monkeypatch.setattr(mcp, "QuarantinedSenseReader", lambda _store: lambda args: {"senses": args})
    monkeypatch.setattr(mcp, "validate_sense_arguments", lambda args: dict(args))
    monkeypatch.setattr(mcp, "request_action", lambda *args, **kwargs: {
        "action": args[1], "arguments": args[2], "origin": (kwargs["channel_id"], kwargs["thread_ts"])
    })

    tools = catalog(tmp_path, senses, action_socket=tmp_path / "action.sock",
                    channel_id="D-1", thread_ts="10.2")
    assert set(tools) == {"weather", "web_search", "web_fetch", "workspace", "senses", "start_coding"}
    assert "sunny" in dispatch(tools, "weather", {"location": "  Manila  "})["content"][0]["text"]
    dispatch(tools, "web_search", {"query": " iris "})
    dispatch(tools, "web_fetch", {"url": "https://example.com"})
    dispatch(tools, "workspace", {"path": "."})
    assert '"senses"' in dispatch(tools, "senses", {})["content"][0]["text"]
    action = json.loads(dispatch(tools, "start_coding", {
        "tool": "claude", "project": "Iris", "task": "test"
    })["content"][0]["text"])
    assert action["data"]["origin"] == ["D-1", "10.2"]
    assert {name for name, _payload in calls} == {"weather", "search", "fetch", "workspace"}


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
    read_spec = next(item for item in tool_specs(tools) if item["name"] == "weather")
    assert "read-only tool" in read_spec["description"]


def test_weather_argument_validation_is_strict_and_bounded():
    assert validate_weather_arguments({"location": "  Manila  "}) == {"location": "Manila"}
    assert len(validate_weather_arguments({"location": "x" * 250})["location"]) == 200
    for arguments in ({}, {"location": ""}, {"location": 3}, {"location": "x", "extra": 1}):
        with pytest.raises(ValueError, match="location is required"):
            validate_weather_arguments(arguments)


def test_dispatch_serializes_result_objects_and_fails_closed():
    result = dispatch({"x": (lambda _args: SimpleNamespace(text="ok", source="src", observed_at="now"), {}, ())},
                      "x", {})
    decoded = json.loads(result["content"][0]["text"])
    assert decoded["data"] == {"text": "ok", "source": "src", "observed_at": "now"}

    def explode(_args):
        raise RuntimeError("secret detail")

    result = dispatch({"x": (explode, {}, ())}, "x", {})
    assert result == {"content": [{"type": "text", "text": "tool is unavailable"}], "isError": True}


def test_agent_action_denial_is_an_mcp_error_not_a_success():
    def denied(_args):
        raise AgentActionError("operator denied the action")

    result = dispatch({"start_coding": (denied, {}, ())}, "start_coding", {})
    assert result["isError"] is True
    assert "operator denied the action" in result["content"][0]["text"]


def test_mcp_server_denies_unknown_or_malformed_tool_calls():
    assert dispatch({}, "write_file", {})["isError"] is True
    assert dispatch({"x": (lambda _args: None, {}, ())}, "x", "not-an-object")["isError"] is True


def test_stdio_server_handles_initialize_list_call_and_bad_input(monkeypatch):
    tools = {"echo": (lambda args: args, {"value": {"type": "string"}}, ("value",))}
    requests = [
        {"jsonrpc": "2.0", "id": 1, "method": "initialize"},
        {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
        {"jsonrpc": "2.0", "id": 3, "method": "tools/call",
         "params": {"name": "echo", "arguments": {"value": "hello"}}},
        {"jsonrpc": "2.0", "id": 4, "method": "tools/call", "params": []},
        {"jsonrpc": "2.0", "id": 5, "method": "unknown"},
    ]
    stdin = "not-json\n" + "\n".join(json.dumps(item) for item in requests) + "\n"
    output = io.StringIO()
    monkeypatch.setattr(sys, "stdin", io.StringIO(stdin))
    monkeypatch.setattr(sys, "stdout", output)

    mcp.serve(tools)

    replies = [json.loads(line) for line in output.getvalue().splitlines()]
    assert [reply["id"] for reply in replies] == [1, 2, 3]
    assert replies[0]["result"]["serverInfo"] == {"name": "iris", "version": "1"}
    assert replies[1]["result"]["tools"][0]["name"] == "echo"
    assert '"hello"' in replies[2]["result"]["content"][0]["text"]


def test_mcp_main_passes_cli_origin_to_catalog_and_serve(monkeypatch, tmp_path):
    captured = {}

    def fake_catalog(workspace_root, senses_path, **kwargs):
        captured["catalog"] = (workspace_root, senses_path, kwargs)
        return {"fake": object()}

    monkeypatch.setattr(mcp, "catalog", fake_catalog)
    monkeypatch.setattr(mcp, "serve", lambda tools: captured.setdefault("served", tools))
    monkeypatch.setattr(sys, "argv", [
        "iris.mcp_server",
        "--workspace-root", str(tmp_path),
        "--senses-path", str(tmp_path / "senses.json"),
        "--action-socket", str(tmp_path / "action.sock"),
        "--channel-id", "D1",
        "--thread-ts", "1.0",
    ])

    assert mcp.main() == 0
    root, senses, kwargs = captured["catalog"]
    assert root == str(tmp_path)
    assert senses == str(tmp_path / "senses.json")
    assert kwargs == {
        "action_socket": str(tmp_path / "action.sock"),
        "channel_id": "D1",
        "thread_ts": "1.0",
    }
    assert set(captured["served"]) == {"fake"}
