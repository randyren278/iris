"""Bounded, non-executing conversational turns for allowlisted Slack DMs."""
from __future__ import annotations

import dataclasses
import json
import os
import subprocess
from collections import defaultdict, deque


@dataclasses.dataclass(frozen=True)
class MemoryContext:
    text: str
    trust: str
    provenance: str


@dataclasses.dataclass(frozen=True)
class ConversationMessage:
    role: str
    text: str


# A conversational turn is short and tool-less, so it does not need the coding
# model. Pinning it here makes the choice explicit rather than inheriting
# whatever the operator's CLI happens to default to.
CONVERSATION_MODEL = "sonnet"

# Without these, a nested `claude -p` loads the operator's settings files and
# runs their hooks, which sends raw DM transcripts wherever those hooks point
# and injects unrelated context into Iris's prompt. Bare mode is deliberately
# not used here: it skips keychain reads and would break subscription auth.
CLAUDE_ISOLATION = ["--setting-sources", "", "--strict-mcp-config"]


class ClaudeTextBackend:
    """A text-only Claude turn. Tool use remains behind explicit Iris controls."""

    def __init__(self, *, run=subprocess.run, timeout=90, environ=None):
        self._run = run
        self.timeout = timeout
        self._environ = dict(os.environ if environ is None else environ)

    def reply(self, messages: tuple[ConversationMessage, ...], context: tuple[MemoryContext, ...]) -> str:
        prompt = _prompt(messages, context)
        try:
            result = self._run(
                ["claude", "--model", CONVERSATION_MODEL, "--permission-mode", "manual",
                 "--tools", "", *CLAUDE_ISOLATION, "-p", "--output-format", "json", prompt],
                capture_output=True, text=True, timeout=self.timeout, check=False,
                env={key: value for key, value in self._environ.items() if not key.startswith("CLAUDE")},
            )
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return "Iris's conversation backend is temporarily unavailable. Please try again shortly."
        if result.returncode != 0:
            return "I couldn't complete that conversational turn. Please try again."
        try:
            response = json.loads(result.stdout).get("result", "")
        except json.JSONDecodeError:
            response = result.stdout
        return response.strip() or "I don't have a response for that yet."


class ConversationCoordinator:
    """Per-thread short-term context; it returns prose and never dispatches actions."""

    def __init__(self, backend, *, context_provider=None, max_messages=8):
        self.backend = backend
        self.context_provider = context_provider or (lambda _key: ())
        self.max_messages = max_messages
        self._turns: dict[tuple[str, str], deque[ConversationMessage]] = defaultdict(deque)

    def reply(self, message) -> str:
        key = (message.channel_id, message.reply_thread_ts)
        turns = self._turns[key]
        turns.append(ConversationMessage("user", message.text))
        try:
            supplied = self.context_provider(key, message.text)
        except TypeError:  # compatibility for existing one-argument providers
            supplied = self.context_provider(key)
        context = tuple(item for item in supplied if item.trust in {"self", "team"})
        reply = self.backend.reply(tuple(turns), context)
        turns.append(ConversationMessage("assistant", reply))
        while len(turns) > self.max_messages:
            turns.popleft()
        return reply


def _prompt(messages: tuple[ConversationMessage, ...], context: tuple[MemoryContext, ...]) -> str:
    trusted = "\n".join(f"- [{item.trust}; {item.provenance}] {item.text}" for item in context)
    transcript = "\n".join(f"{item.role}: {item.text}" for item in messages)
    return (
        "You are Iris, a local-first personal assistant in a private Slack DM.\n\n"
        "Non-negotiable: you have no tools in this turn and must not claim to have performed an "
        "action. The user's plain-English request is not itself an action trigger. If the user "
        "wants something done, explain the explicit Iris command or ask for confirmation; "
        "consequential work goes only through Iris's approval controls.\n\n"
        "Voice: be concise, direct, observant, and naturally conversational. Mirror the user's "
        "tone, casing, and emoji level; don't force lowercase. Notice what's actually "
        "interesting or funny in what the user says and say so; dry, observational humor is "
        "welcome when it fits the moment. Warmth is earned, not sycophantic. Occasional light "
        "teasing is fine when it's clearly welcome and relevant, but never mean-spirited or "
        "distracting, and never inside a safety-sensitive reply — including but not limited to "
        "anything urgent or about stopping work, an approval explanation, a decline, an "
        "error/failure explanation, or anything touching credentials or private data.\n\n"
        f"Trusted context:\n{trusted or '(none)'}\n\nConversation:\n{transcript}"
    )
