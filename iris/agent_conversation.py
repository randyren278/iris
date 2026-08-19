"""Conversation adapter that gives Iris's general runtime thread-local context."""
from __future__ import annotations

import json
import pathlib
import subprocess
import sys
from collections import defaultdict, deque

from iris.agent_runtime import AgentReply, AgentRuntime
from iris.conversation import CLAUDE_ISOLATION, CONVERSATION_MODEL, ConversationMessage, _prompt


class ClaudeMCPAgentAdapter:
    """Run an isolated Claude turn with only Iris-owned MCP read tools."""

    TOOL_NAMES = ("mcp__iris__weather", "mcp__iris__web_search", "mcp__iris__web_fetch",
                  "mcp__iris__workspace", "mcp__iris__senses")

    def __init__(self, workspace_root, senses_path, turns, context, *, run=subprocess.run, timeout=90):
        self._workspace_root = str(pathlib.Path(workspace_root).resolve())
        self._senses_path = str(pathlib.Path(senses_path))
        self._turns, self._context = turns, context
        self._run, self._timeout = run, timeout

    def command(self) -> list[str]:
        config = {"mcpServers": {"iris": {"command": sys.executable, "args": [
            "-m", "iris.mcp_server", "--workspace-root", self._workspace_root,
            "--senses-path", self._senses_path,
        ]}}}
        return ["claude", "--model", CONVERSATION_MODEL, "--permission-mode", "manual",
                "--tools", ",".join(self.TOOL_NAMES), *CLAUDE_ISOLATION,
                "--mcp-config", json.dumps(config, separators=(",", ":")), "--strict-mcp-config",
                "-p", "--output-format", "json", _prompt(self._turns, self._context)]

    def next_step(self, _user_text, _results):
        try:
            result = self._run(self.command(), capture_output=True, text=True, timeout=self._timeout, check=False)
        except (OSError, subprocess.TimeoutExpired):
            return AgentReply("Iris's agent runtime is temporarily unavailable. Please try again shortly.")
        if result.returncode != 0:
            return AgentReply("I couldn't complete that agent turn. Please try again.")
        try:
            text = json.loads(result.stdout).get("result", "")
        except json.JSONDecodeError:
            text = result.stdout
        return AgentReply(text.strip() or "I don't have a response for that yet.")


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
