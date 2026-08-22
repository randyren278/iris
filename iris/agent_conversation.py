"""Conversation adapter that gives Iris's general runtime thread-local context."""
from __future__ import annotations

import json
import os
import pathlib
import subprocess
import threading
from collections import defaultdict, deque

from iris.agent_runtime import AgentReply, AgentRuntime
from iris.mcp_server import catalog, json_safe, tool_specs
from iris.conversation import CLAUDE_ISOLATION, CONVERSATION_MODEL, ConversationMessage, _agent_prompt
from iris.tool_protocol import ProtocolError, ToolRequest


def _json_safe_handler(handler):
    return lambda arguments: json_safe(handler(arguments))


def _tool_request_or_none(text: str) -> ToolRequest | None:
    """Read a tool request out of a model turn, or decide the turn is an answer.

    The model is asked for a bare JSON object, but wrapping it in a fenced code
    block is the common near-miss, so unwrap that one case. Anything else is
    prose and is treated as the final answer -- a malformed request must never
    become a tool call.
    """
    candidate = text.strip()
    if candidate.startswith("```"):
        body = candidate.split("```")[1] if candidate.count("```") >= 2 else ""
        candidate = body.split("\n", 1)[-1].strip() if body.startswith("json") else body.strip()
    if not candidate.startswith("{"):
        return None
    try:
        return ToolRequest.from_json(candidate)
    except ProtocolError:
        return None


class ClaudeToolAgentAdapter:
    """Plan one bounded turn with an isolated Claude process; Iris runs the tools.

    The model never receives a tool handle. It is shown the catalog and may
    emit a ``tool_request``, which ``AgentRuntime`` validates and dispatches to
    Iris-owned handlers inside this process. Iris owning dispatch is what lets
    the nested command keep ``--setting-sources ""`` and ``--tools ""``: the
    CLI's own MCP delivery requires operator settings to be loaded, which would
    run the operator's hooks over raw DM text.
    """

    def __init__(self, workspace_root, senses_path, turns, context, *, action_socket=None,
                 channel_id=None, thread_ts=None, run=subprocess.run, timeout=90, environ=None):
        self._workspace_root = str(pathlib.Path(workspace_root).resolve())
        self._senses_path = str(pathlib.Path(senses_path))
        self._action_socket = str(action_socket) if action_socket else None
        self._channel_id = channel_id
        self._thread_ts = thread_ts
        self._turns, self._context = turns, context
        self._run, self._timeout = run, timeout
        self._environ = dict(os.environ if environ is None else environ)
        # One catalog per turn: it carries this thread's approval origin, and
        # it is the same catalog the MCP server builds, so tool names, schemas,
        # and argument validation cannot drift between the two.
        self._tools = catalog(
            self._workspace_root, self._senses_path,
            action_socket=self._action_socket, channel_id=channel_id, thread_ts=thread_ts,
        )

    @property
    def tool_names(self) -> tuple[str, ...]:
        return tuple(self._tools)

    def handlers(self) -> dict:
        """The tools Iris will run for this turn. Only AgentRuntime invokes them.

        Results are converted to plain JSON data on the way out, because the
        next planning turn renders them into a prompt.
        """
        return {name: _json_safe_handler(entry[0]) for name, entry in self._tools.items()}

    def command(self, results=()) -> list[str]:
        return ["claude", "--model", CONVERSATION_MODEL, "--permission-mode", "manual",
                "--tools", "", *CLAUDE_ISOLATION,
                "--no-session-persistence", "-p", "--output-format", "json",
                self.prompt(results)]

    def prompt(self, results=()) -> str:
        catalog_text = json.dumps(tool_specs(self._tools), separators=(",", ":"), sort_keys=True)
        observed = "\n".join(result.to_json() for result in results)
        # Reusing a request id is refused outright, because a repeat of a
        # consequential call must never run twice. Naming the spent ids and
        # saying a listed result is final keeps the model from spending the
        # turn on a retry Iris will reject.
        spent = ", ".join(result.request_id for result in results)
        return (
            _agent_prompt(self._turns, self._context,
                          actions_enabled="start_coding" in self._tools)
            + "\n\nTools Iris will run for you:\n" + catalog_text
            + "\n\nTo use one, reply with ONLY this JSON object and no other text:\n"
            + '{"type":"tool_request","request_id":"<new id>",'
              '"tool_name":"<name above>","arguments":{...}}\n'
            + "Otherwise reply with your answer as ordinary text.\n"
            + "Each request_id must be one you have not already used this turn"
            + (f"; already used: {spent}.\n" if spent else ".\n")
            + "A result below is final. Do not repeat a call that already has one -- "
              "use it to answer, and never claim an outcome it does not show.\n\n"
            + ("Tool results so far:\n" + observed if observed else "Tool results so far: (none)")
        )

    def next_step(self, _user_text, results):
        try:
            result = self._run(
                self.command(results), capture_output=True, text=True, timeout=self._timeout,
                check=False,
                env={key: value for key, value in self._environ.items() if not key.startswith("CLAUDE")},
            )
        except (OSError, subprocess.TimeoutExpired):
            return AgentReply("Iris's agent runtime is temporarily unavailable. Please try again shortly.")
        if result.returncode != 0:
            return AgentReply("I couldn't complete that agent turn. Please try again.")
        try:
            text = json.loads(result.stdout).get("result", "")
        except json.JSONDecodeError:
            text = result.stdout
        request = _tool_request_or_none(text)
        if request is not None:
            return request
        return AgentReply(text.strip() or "I don't have a response for that yet.")


class GeneralAgentCoordinator:
    """Thread-aware conversation entrypoint for an agent adapter and Iris runtime."""

    def __init__(self, runtime: AgentRuntime, agent_factory, *, context_provider=None, max_messages=8):
        self._runtime = runtime
        self._agent_factory = agent_factory
        self._context_provider = context_provider or (lambda _key, _text: ())
        self._max_messages = max_messages
        self._turns = defaultdict(deque)
        self._thread_locks = defaultdict(threading.Lock)

    def reply(self, message) -> str:
        key = (message.channel_id, message.reply_thread_ts)
        with self._thread_locks[key]:
            turns = self._turns[key]
            turns.append(ConversationMessage("user", message.text))
            try:
                supplied = self._context_provider(key, message.text)
            except TypeError:
                supplied = self._context_provider(key)
            context = tuple(item for item in supplied if item.trust in {"self", "team"})
            agent = self._agent_factory(message, tuple(turns), context)
            reply = self._runtime.reply(agent, message.text, handlers=agent.handlers())
            turns.append(ConversationMessage("assistant", reply))
            while len(turns) > self._max_messages:
                turns.popleft()
            return reply
