"""Fixed, schema-checked catalog for agent-selected read-only tools."""
from __future__ import annotations

import dataclasses
import enum
from collections.abc import Callable, Mapping

from iris.tool_protocol import ToolRequest, ToolResult


class ToolMode(enum.StrEnum):
    READ_ONLY = "read_only"
    PROPOSAL_ONLY = "proposal_only"
    CONSEQUENTIAL = "consequential"


@dataclasses.dataclass(frozen=True)
class ToolDefinition:
    name: str
    mode: ToolMode
    validate: Callable[[dict[str, object]], dict[str, object]]
    handler: Callable[[dict[str, object]], object]
    provenance: str
    timeout_seconds: float


class ToolCatalog:
    """Only Iris may dispatch catalog entries; all other requests deny safely."""

    def __init__(self, definitions: tuple[ToolDefinition, ...] = ()):
        self._definitions = {item.name: item for item in definitions}

    def names(self) -> tuple[str, ...]:
        return tuple(self._definitions)

    def definition(self, name: str) -> ToolDefinition | None:
        return self._definitions.get(name)

    def invoke(self, request: ToolRequest) -> ToolResult:
        definition = self._definitions.get(request.tool_name)
        if definition is None:
            return ToolResult(request.request_id, error="tool is not available")
        if definition.mode is not ToolMode.READ_ONLY:
            return ToolResult(request.request_id, error="tool requires explicit approval")
        try:
            arguments = definition.validate(dict(request.arguments))
            data = definition.handler(arguments)
        except (TypeError, ValueError):
            return ToolResult(request.request_id, error="tool request was rejected")
        except Exception:
            return ToolResult(request.request_id, error="tool is unavailable")
        return ToolResult(request.request_id, content={
            "data": data,
            "provenance": definition.provenance,
            "trust": "untrusted_external",
        })
