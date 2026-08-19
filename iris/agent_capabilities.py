"""Approval-bound dispatch for agent-selected consequential capabilities."""
from __future__ import annotations

import dataclasses
import hashlib
import json
import secrets
from collections.abc import Callable

from iris.tool_catalog import ToolCatalog, ToolMode
from iris.tool_protocol import ToolRequest, ToolResult


@dataclasses.dataclass(frozen=True)
class BoundToolCall:
    nonce: str
    tool_name: str
    arguments: dict[str, object]
    channel_id: str
    thread_ts: str
    fingerprint: str

    @classmethod
    def create(cls, tool_name: str, arguments: dict[str, object], channel_id: str, thread_ts: str,
               *, nonce: str | None = None) -> "BoundToolCall":
        if not all(isinstance(value, str) and value for value in (tool_name, channel_id, thread_ts)):
            raise ValueError("tool call identity is incomplete")
        immutable = json.loads(json.dumps(arguments, sort_keys=True, separators=(",", ":")))
        payload = json.dumps({"tool_name": tool_name, "arguments": immutable,
                              "channel_id": channel_id, "thread_ts": thread_ts},
                             sort_keys=True, separators=(",", ":"))
        return cls(nonce or secrets.token_urlsafe(24), tool_name, immutable, channel_id, thread_ts,
                   hashlib.sha256(payload.encode()).hexdigest())

    def summary(self) -> str:
        return (f"Agent request {self.nonce}: {self.tool_name}({json.dumps(self.arguments, sort_keys=True)}) "
                f"in {self.channel_id}/{self.thread_ts}. Approve this exact request only.")


class AgentApprovalGate:
    """Consume one approval nonce for the exact tool arguments and origin thread."""

    def __init__(self, request_approval: Callable[[str, float], bool], *, nonce_factory=secrets.token_urlsafe):
        self._request_approval = request_approval
        self._nonce_factory = nonce_factory
        self._consumed: set[str] = set()

    @classmethod
    def from_queue(cls, queue, notifier: Callable[[str], None], *, nonce_factory=secrets.token_urlsafe):
        """Bind approval delivery to the originating Slack thread's notifier."""
        return cls(lambda summary, timeout: queue.request(summary, timeout=timeout, notifier=notifier),
                   nonce_factory=nonce_factory)

    def bind(self, tool_name: str, arguments: dict[str, object], channel_id: str, thread_ts: str) -> BoundToolCall:
        return BoundToolCall.create(tool_name, arguments, channel_id, thread_ts, nonce=self._nonce_factory(24))

    def request(self, call: BoundToolCall, *, timeout: float) -> bool:
        if call.nonce in self._consumed or not call.fingerprint:
            return False
        self._consumed.add(call.nonce)
        try:
            return self._request_approval(call.summary(), timeout) is True
        except Exception:
            return False


class AgentCapabilityExecutor:
    """Enforce catalog-owned authority before agent calls reach any handler."""

    def __init__(self, catalog: ToolCatalog, approvals: AgentApprovalGate):
        self._catalog = catalog
        self._approvals = approvals

    def invoke(self, request: ToolRequest, *, channel_id: str, thread_ts: str, timeout: float = 120.0) -> ToolResult:
        definition = self._catalog.definition(request.tool_name)
        if definition is None:
            return ToolResult(request.request_id, error="tool is not available")
        if definition.mode is ToolMode.READ_ONLY:
            return self._catalog.invoke(request)
        if definition.mode is ToolMode.PROPOSAL_ONLY:
            return ToolResult(request.request_id, error="tool requires an explicit Iris command")
        try:
            arguments = definition.validate(dict(request.arguments))
            call = self._approvals.bind(definition.name, arguments, channel_id, thread_ts)
        except (TypeError, ValueError):
            return ToolResult(request.request_id, error="tool request was rejected")
        if not self._approvals.request(call, timeout=timeout):
            return ToolResult(request.request_id, error="tool request was denied")
        try:
            return ToolResult(request.request_id, content=definition.handler(call.arguments))
        except Exception:
            return ToolResult(request.request_id, error="tool is unavailable")
