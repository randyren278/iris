"""Validated messages exchanged between an Iris-owned agent runtime and tools.

The agent may select a tool by name and supply JSON arguments.  It never gets
a process handle or a path to a provider: Iris validates its request and owns
the dispatch boundary.
"""
from __future__ import annotations

import dataclasses
import json
from collections.abc import Mapping
from typing import Any


class ProtocolError(ValueError):
    """A message did not conform to Iris's fixed agent/tool protocol."""


def _object(value: object, *, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ProtocolError(f"{label} must be an object")
    return value


def _string(value: object, *, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise ProtocolError(f"{label} must be a non-empty string")
    return value


@dataclasses.dataclass(frozen=True)
class ToolRequest:
    request_id: str
    tool_name: str
    arguments: dict[str, object]

    @classmethod
    def from_json(cls, raw: str) -> "ToolRequest":
        try:
            value = json.loads(raw)
        except (TypeError, json.JSONDecodeError) as error:
            raise ProtocolError("request is not JSON") from error
        data = _object(value, label="request")
        if set(data) != {"type", "request_id", "tool_name", "arguments"}:
            raise ProtocolError("request has unsupported fields")
        if data["type"] != "tool_request":
            raise ProtocolError("request type is invalid")
        arguments = _object(data["arguments"], label="arguments")
        if not all(isinstance(key, str) for key in arguments):
            raise ProtocolError("argument names must be strings")
        return cls(_string(data["request_id"], label="request_id"),
                   _string(data["tool_name"], label="tool_name"), arguments)

    def to_json(self) -> str:
        return json.dumps({"type": "tool_request", "request_id": self.request_id,
                           "tool_name": self.tool_name, "arguments": self.arguments},
                          separators=(",", ":"), sort_keys=True)


@dataclasses.dataclass(frozen=True)
class ToolResult:
    request_id: str
    content: object | None = None
    error: str | None = None

    def __post_init__(self) -> None:
        if bool(self.content is None) == bool(self.error is None):
            raise ProtocolError("tool result must contain exactly one of content or error")
        if self.error is not None and not isinstance(self.error, str):
            raise ProtocolError("tool result error must be text")

    @classmethod
    def from_json(cls, raw: str) -> "ToolResult":
        try:
            value = json.loads(raw)
        except (TypeError, json.JSONDecodeError) as error:
            raise ProtocolError("result is not JSON") from error
        data = _object(value, label="result")
        if set(data) - {"type", "request_id", "content", "error"} or data.get("type") != "tool_result":
            raise ProtocolError("result has unsupported fields")
        if "content" not in data and "error" not in data:
            raise ProtocolError("result is incomplete")
        return cls(_string(data.get("request_id"), label="request_id"),
                   data.get("content"), data.get("error"))

    def to_json(self) -> str:
        body: dict[str, object] = {"type": "tool_result", "request_id": self.request_id}
        body["error" if self.error is not None else "content"] = self.error if self.error is not None else self.content
        return json.dumps(body, separators=(",", ":"), sort_keys=True)
