"""Iris-owned stepping runtime for a local tool-using agent.

This deliberately contains no subprocess or provider access.  An adapter can
ask for a registered tool, but only this runtime invokes the associated Iris
handler and returns a structured result to the adapter.
"""
from __future__ import annotations

import dataclasses
from collections.abc import Callable, Mapping
from typing import Protocol

from iris.tool_protocol import ProtocolError, ToolRequest, ToolResult


class AgentProtocolError(RuntimeError):
    """A local agent adapter emitted an invalid step."""


@dataclasses.dataclass(frozen=True)
class AgentReply:
    text: str


class AgentAdapter(Protocol):
    def next_step(self, user_text: str, results: tuple[ToolResult, ...]) -> ToolRequest | AgentReply: ...


class AgentRuntime:
    """Run bounded agent/tool steps while retaining sole ownership of tools."""

    def __init__(self, handlers: Mapping[str, Callable[[dict[str, object]], object]], *, max_steps: int = 4):
        self._handlers = dict(handlers)
        self._max_steps = max_steps

    def reply(self, agent: AgentAdapter, user_text: str, *,
              handlers: Mapping[str, Callable[[dict[str, object]], object]] | None = None) -> str:
        """Answer one turn, dispatching any tool the agent asks for.

        ``handlers`` supplies the tools for this turn only. Some are bound to
        the originating Slack thread, so they cannot be registered once at
        startup; building them per turn keeps concurrent threads from sharing
        an origin. Turn handlers layer over the ones registered at
        construction and are never stored.
        """
        if not isinstance(user_text, str) or not user_text:
            raise AgentProtocolError("user text is required")
        available = {**self._handlers, **(handlers or {})}
        results: list[ToolResult] = []
        seen_ids: set[str] = set()
        for _step in range(self._max_steps):
            message = agent.next_step(user_text, tuple(results))
            if isinstance(message, AgentReply):
                if not message.text:
                    raise AgentProtocolError("agent reply is empty")
                return message.text
            if not isinstance(message, ToolRequest):
                raise AgentProtocolError("agent emitted an invalid message")
            if message.request_id in seen_ids:
                raise AgentProtocolError("agent reused a tool request id")
            seen_ids.add(message.request_id)
            results.append(self._invoke(message, available))
        raise AgentProtocolError("agent exceeded the tool-step limit")

    def _invoke(self, request: ToolRequest, handlers) -> ToolResult:
        handler = handlers.get(request.tool_name)
        if handler is None:
            return ToolResult(request.request_id, error="tool is not available")
        try:
            return ToolResult(request.request_id, content=handler(dict(request.arguments)))
        except (ProtocolError, ValueError, TypeError):
            return ToolResult(request.request_id, error="tool request was rejected")
        except Exception:
            return ToolResult(request.request_id, error="tool is unavailable")
