import json
from types import SimpleNamespace

from iris.agent_conversation import ClaudeMCPAgentAdapter
from iris.conversation import ConversationMessage


def test_production_adapter_isolates_claude_and_registers_only_iris_mcp_tools(tmp_path):
    adapter = ClaudeMCPAgentAdapter(tmp_path, tmp_path / "senses.json", (ConversationMessage("user", "weather"),), ())
    command = adapter.command()
    assert "--strict-mcp-config" in command
    assert command[command.index("--tools") + 1] == ",".join(adapter.TOOL_NAMES)
    config = json.loads(command[command.index("--mcp-config") + 1])
    assert config["mcpServers"]["iris"]["args"][:2] == ["-m", "iris.mcp_server"]


def test_production_adapter_returns_agent_result_after_mcp_turn(tmp_path):
    adapter = ClaudeMCPAgentAdapter(tmp_path, tmp_path / "senses.json", (), (),
                                   run=lambda *_args, **_kwargs: SimpleNamespace(returncode=0, stdout='{"result":"29°C"}'))
    assert adapter.next_step("weather", ()).text == "29°C"
