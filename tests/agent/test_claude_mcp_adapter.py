import json
from types import SimpleNamespace

from iris.agent_conversation import ClaudeMCPAgentAdapter
from iris.conversation import ConversationMessage


def test_production_adapter_isolates_claude_and_registers_only_iris_mcp_tools(tmp_path):
    adapter = ClaudeMCPAgentAdapter(tmp_path, tmp_path / "senses.json", (ConversationMessage("user", "weather"),), ())
    command = adapter.command()
    assert "--strict-mcp-config" in command
    assert command[command.index("--tools") + 1] == ",".join(adapter.tool_names)
    assert command[command.index("--allowedTools") + 1] == ",".join(adapter.tool_names)
    assert "mcp__iris__senses" not in adapter.tool_names
    assert "no tools in this turn" not in command[-1]
    assert "Use them when they are relevant" in command[-1]
    config = json.loads(command[command.index("--mcp-config") + 1])
    assert config["mcpServers"]["iris"]["args"][:2] == ["-m", "iris.mcp_server"]


def test_production_adapter_returns_agent_result_after_mcp_turn(tmp_path):
    adapter = ClaudeMCPAgentAdapter(tmp_path, tmp_path / "senses.json", (), (),
                                   run=lambda *_args, **_kwargs: SimpleNamespace(returncode=0, stdout='{"result":"29°C"}'))
    assert adapter.next_step("weather", ()).text == "29°C"


def test_production_adapter_does_not_inherit_claude_environment(tmp_path):
    captured = {}
    def run(*_args, **kwargs):
        captured.update(kwargs)
        return SimpleNamespace(returncode=0, stdout='{"result":"ok"}')
    adapter = ClaudeMCPAgentAdapter(tmp_path, tmp_path / "senses.json", (), (), run=run,
                                   environ={"PATH": "safe", "CLAUDE_CODE_HOOK": "unsafe"})
    adapter.next_step("hello", ())
    assert captured["env"] == {"PATH": "safe"}


def test_production_adapter_exposes_senses_only_when_store_exists(tmp_path):
    path = tmp_path / "senses.json"
    path.write_text("[]")
    assert "mcp__iris__senses" in ClaudeMCPAgentAdapter(tmp_path, path, (), ()).tool_names
