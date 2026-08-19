"""Conversation adapter that gives Iris's general runtime thread-local context."""
from __future__ import annotations

from collections import defaultdict, deque

from iris.agent_runtime import AgentReply, AgentRuntime
from iris.conversation import ConversationMessage, MemoryContext


class TextOnlyAgentAdapter:
    """Temporary adapter for ordinary prose until the live MCP adapter is enabled."""

    def __init__(self, backend, turns, context):
        self._backend, self._turns, self._context = backend, turns, context

    def next_step(self, _user_text, _results):
        return AgentReply(self._backend.reply(self._turns, self._context))


class GeneralAgentCoordinator:
    """Thread-aware conversation entrypoint for an agent adapter and Iris runtime."""

    def __init__(self, runtime: AgentRuntime, agent_factory, *, context_provider=None, max_messages=8):
        self._runtime = runtime
        self._agent_factory = agent_factory
        self._context_provider = context_provider or (lambda _key, _text: ())
        self._max_messages = max_messages
        self._turns = defaultdict(deque)

    def reply(self, message) -> str:
        key = (message.channel_id, message.reply_thread_ts)
        turns = self._turns[key]
        turns.append(ConversationMessage("user", message.text))
        try:
            supplied = self._context_provider(key, message.text)
        except TypeError:
            supplied = self._context_provider(key)
        context = tuple(item for item in supplied if item.trust in {"self", "team"})
        agent = self._agent_factory(message, tuple(turns), context)
        reply = self._runtime.reply(agent, message.text)
        turns.append(ConversationMessage("assistant", reply))
        while len(turns) > self._max_messages:
            turns.popleft()
        return reply
