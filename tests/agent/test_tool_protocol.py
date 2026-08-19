import pytest

from iris.tool_protocol import ProtocolError, ToolRequest, ToolResult


def test_tool_request_round_trip_preserves_only_structured_fields():
    request = ToolRequest("r-1", "workspace", {"path": "README.md"})
    assert ToolRequest.from_json(request.to_json()) == request


@pytest.mark.parametrize("raw", [
    "not json",
    '{"type":"tool_request","request_id":"r","tool_name":"x","arguments":{},"extra":true}',
    '{"type":"tool_request","request_id":"r","tool_name":"x","arguments":[]}',
])
def test_tool_request_rejects_malformed_messages(raw):
    with pytest.raises(ProtocolError):
        ToolRequest.from_json(raw)


def test_tool_result_requires_exactly_one_result_variant():
    with pytest.raises(ProtocolError):
        ToolResult("r", content="ok", error="no")
    assert ToolResult.from_json('{"type":"tool_result","request_id":"r","error":"denied"}').error == "denied"
