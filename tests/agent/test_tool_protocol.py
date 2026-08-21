import json

import pytest

from iris.tool_protocol import ProtocolError, ToolRequest, ToolResult, _object, _string


def test_protocol_primitive_validators_are_strict():
    assert _object({"x": 1}, label="thing") == {"x": 1}
    with pytest.raises(ProtocolError, match="thing must be an object"):
        _object([], label="thing")
    assert _string("x", label="name") == "x"
    for value in ("", None, 3, True):
        with pytest.raises(ProtocolError, match="name must be a non-empty string"):
            _string(value, label="name")


def test_tool_request_round_trip_preserves_only_structured_fields():
    request = ToolRequest("r-1", "workspace", {"path": "README.md", "nested": {"ok": True}})
    raw = request.to_json()
    assert ToolRequest.from_json(raw) == request
    assert json.loads(raw) == {
        "type": "tool_request",
        "request_id": "r-1",
        "tool_name": "workspace",
        "arguments": {"nested": {"ok": True}, "path": "README.md"},
    }


@pytest.mark.parametrize("raw, match", [
    ("not json", "request is not JSON"),
    (None, "request is not JSON"),
    ("[]", "request must be an object"),
    ('{"type":"tool_request","request_id":"r","tool_name":"x","arguments":{},"extra":true}',
     "unsupported fields"),
    ('{"type":"wrong","request_id":"r","tool_name":"x","arguments":{}}', "request type is invalid"),
    ('{"type":"tool_request","request_id":"r","tool_name":"x","arguments":[]}', "arguments must be an object"),
    ('{"type":"tool_request","request_id":"","tool_name":"x","arguments":{}}', "request_id must be"),
    ('{"type":"tool_request","request_id":"r","tool_name":"","arguments":{}}', "tool_name must be"),
])
def test_tool_request_rejects_malformed_messages(raw, match):
    with pytest.raises(ProtocolError, match=match):
        ToolRequest.from_json(raw)


def test_tool_request_rejects_non_string_argument_names_without_relying_on_json_parser():
    # JSON itself cannot represent a non-string object key, so exercise the
    # post-decode invariant by monkeypatching the decoder.
    import iris.tool_protocol as protocol
    original = protocol.json.loads
    protocol.json.loads = lambda _raw: {
        "type": "tool_request", "request_id": "r", "tool_name": "x", "arguments": {1: "bad"}
    }
    try:
        with pytest.raises(ProtocolError, match="argument names must be strings"):
            ToolRequest.from_json("ignored")
    finally:
        protocol.json.loads = original


def test_tool_result_requires_exactly_one_result_variant_and_text_errors():
    with pytest.raises(ProtocolError, match="exactly one"):
        ToolResult("r")
    with pytest.raises(ProtocolError, match="exactly one"):
        ToolResult("r", content="ok", error="no")
    with pytest.raises(ProtocolError, match="error must be text"):
        ToolResult("r", error=3)

    content = ToolResult("r1", content={"value": 1})
    error = ToolResult("r2", error="denied")
    assert ToolResult.from_json(content.to_json()) == content
    assert ToolResult.from_json(error.to_json()) == error
    assert json.loads(content.to_json()) == {
        "type": "tool_result", "request_id": "r1", "content": {"value": 1}
    }
    assert json.loads(error.to_json()) == {
        "type": "tool_result", "request_id": "r2", "error": "denied"
    }


@pytest.mark.parametrize("raw, match", [
    ("bad", "result is not JSON"),
    (None, "result is not JSON"),
    ("[]", "result must be an object"),
    ('{"type":"wrong","request_id":"r","content":"x"}', "unsupported fields"),
    ('{"type":"tool_result","request_id":"r","content":"x","extra":1}', "unsupported fields"),
    ('{"type":"tool_result","request_id":"r"}', "result is incomplete"),
    ('{"type":"tool_result","request_id":"","content":"x"}', "request_id must be"),
    ('{"type":"tool_result","request_id":"r","content":"x","error":"no"}', "exactly one"),
    ('{"type":"tool_result","request_id":"r","error":3}', "error must be text"),
])
def test_tool_result_rejects_malformed_messages(raw, match):
    with pytest.raises(ProtocolError, match=match):
        ToolResult.from_json(raw)
