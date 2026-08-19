from iris.agent_runtime import AgentReply
from iris.tool_catalog import ToolCatalog, ToolDefinition, ToolMode
from iris.tool_protocol import ToolRequest


def _valid(arguments):
    return arguments


def test_same_agent_protocol_selects_multiple_catalog_tools_without_keyword_routing():
    catalog = ToolCatalog((
        ToolDefinition("web_search", ToolMode.READ_ONLY, _valid, lambda args: {"result": args["q"]}, "web", 2),
        ToolDefinition("workspace", ToolMode.READ_ONLY, _valid, lambda args: {"path": args["path"]}, "workspace", 2),
    ))

    first = catalog.invoke(ToolRequest("one", "web_search", {"q": "iris"}))
    second = catalog.invoke(ToolRequest("two", "workspace", {"path": "README.md"}))

    assert first.content["data"] == {"result": "iris"}
    assert second.content["data"] == {"path": "README.md"}
    assert first.content["trust"] == second.content["trust"] == "untrusted_external"


def test_catalog_does_not_dispatch_proposal_or_consequential_entries():
    called = []
    catalog = ToolCatalog((ToolDefinition("write", ToolMode.CONSEQUENTIAL, _valid,
                                           lambda args: called.append(args), "local", 2),))
    result = catalog.invoke(ToolRequest("one", "write", {"path": "x"}))
    assert result.error == "tool requires explicit approval"
    assert called == []
