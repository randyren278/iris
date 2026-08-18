"""Controlled local launchers for Claude Code and Codex."""
from __future__ import annotations

import os
import pathlib
import json
import shlex
import subprocess
import sys


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
            command = ["claude", "--permission-mode", "manual", "--remote-control"]
            if self._streaming:
                command = ["claude", "--permission-mode", "manual", "--input-format", "stream-json",
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
            return command if self._streaming else [*command, prompt]
        return ["codex", prompt]
