import json
from types import SimpleNamespace

from iris.agent_probe import _tool_names, command, probe


def test_probe_command_uses_only_isolated_disposable_mcp_configuration():
    built = command()
    assert "--setting-sources" in built and "--strict-mcp-config" in built
    config = json.loads(built[built.index("--mcp-config") + 1])
    assert config["mcpServers"]["iris-probe"]["args"] == ["-m", "iris.agent_probe_server"]


def test_probe_requires_both_fake_tool_events_without_printing_payloads():
    output = "\n".join(json.dumps({"type": "tool_use", "name": name}) for name in (
        "mcp__iris-probe__iris_probe_read", "mcp__iris-probe__iris_probe_write"))
    result = probe(lambda *_args, **_kwargs: SimpleNamespace(returncode=0, stdout=output))
    assert result == "Agent runtime probe succeeded: read-only call completed and mutation was denied."


def test_probe_finds_tool_events_nested_in_stream_messages():
    assert _tool_names({"message": {"content": [{"type": "tool_use", "name": "mcp__iris-probe__iris_probe_read"}]}}) == {
        "mcp__iris-probe__iris_probe_read"
    }
