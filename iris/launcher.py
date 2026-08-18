"""Controlled local launchers for Claude Code and Codex."""
from __future__ import annotations

import os
import pathlib
import json
import shlex
import subprocess
import sys

from iris.conversation import CLAUDE_ISOLATION

# Coding sessions do the hard work, so they get the strong model. Codex is left
# unpinned on purpose: it takes its model from ~/.codex/config.toml, so that
# choice stays in one place.
CODING_MODEL = "opus"

# Iris mediates Claude tool calls through the approval socket, but has no
# equivalent hook for Codex, so the sandbox is the boundary instead: a Codex
# session may write inside its project and nowhere else.
CODEX_SANDBOX = "workspace-write"


class Launcher:
    def __init__(self, *, popen=subprocess.Popen, environ=None, approval_socket=None,
                 hook_python=None, streaming=False):
        self._popen = popen
        self._environ = dict(os.environ if environ is None else environ)
        self._approval_socket = str(approval_socket) if approval_socket else None
        self._hook_python = hook_python or sys.executable
        self._streaming = streaming

    def launch(self, tool: str, *, cwd: pathlib.Path | str, prompt: str):
        directory = pathlib.Path(cwd).resolve()
        if tool not in {"claude", "codex"}:
            raise ValueError("unsupported tool")
        if not directory.is_dir():
            raise ValueError("launch cwd is not a directory")
        if not isinstance(prompt, str) or not prompt.strip():
            raise ValueError("prompt is required")
        command = self._command(tool, prompt)
        environment = {key: value for key, value in self._environ.items()
                       if not key.startswith("CLAUDE")}
        if self._approval_socket:
            environment["IRIS_APPROVAL_SOCKET"] = self._approval_socket
        options = {"cwd": str(directory), "env": environment, "start_new_session": True}
        if self._streaming and tool == "claude":
            options.update(stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                           text=True, bufsize=1)
        return self._popen(command, **options)

    def _command(self, tool: str, prompt: str) -> list[str]:
        if tool == "claude":
            # Isolation here is a safety boundary, not tidiness: an operator
            # settings file must not be able to alter the tool-approval path
            # that --settings installs below.
            base = ["claude", "--model", CODING_MODEL, "--permission-mode", "manual",
                    *CLAUDE_ISOLATION]
            command = [*base, "--remote-control"]
            if self._streaming:
                command = [*base, "--input-format", "stream-json",
                           "--output-format", "stream-json", "--include-partial-messages", "--print",
                           "--verbose"]
            if self._approval_socket:
                hook = f"{shlex.quote(self._hook_python)} -m iris.approval_hook"
                settings = {
                    "hooks": {"PreToolUse": [{"matcher": "*", "hooks": [{
                        "type": "command", "command": hook,
                    }]}]}
                }
                command.extend(["--settings", json.dumps(settings, separators=(",", ":"))])
            # "--" marks end-of-options so a prompt that happens to spell a
            # real flag (e.g. "--dangerously-skip-permissions") is parsed as
            # literal text, never as that flag.
            return command if self._streaming else [*command, "--", prompt]
        # `codex exec` is the non-interactive form; the bare interactive CLI
        # exits with "stdin is not a terminal" under launchd. --sandbox on the
        # command line overrides sandbox_mode in ~/.codex/config.toml, so an
        # operator's danger-full-access setting cannot widen an Iris session.
        # The model stays unpinned and comes from that same config. "--"
        # keeps a prompt that spells a real flag (e.g.
        # "--dangerously-bypass-approvals-and-sandbox") from being parsed as
        # that flag instead of literal text.
        return ["codex", "exec", "--sandbox", CODEX_SANDBOX, "--skip-git-repo-check",
                "--json", "--", prompt]
