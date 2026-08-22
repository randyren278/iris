"""Approval-bound consequential actions requested by Iris's general agent."""
from __future__ import annotations

import json
import os
import pathlib
import socket
import threading
from collections.abc import Callable

from iris.projects import ProjectQueryError
from iris.sessions import GatewayDisarmedError

MAX_PROJECT_CHARS = 200
MAX_TASK_CHARS = 4000


class AgentActionError(RuntimeError):
    """A safe failure returned across the local agent-action boundary."""


def validate_start_coding(arguments: dict[str, object]) -> dict[str, str]:
    if set(arguments) != {"tool", "project", "task"}:
        raise ValueError("start_coding requires tool, project, and task")
    tool, project, task = arguments["tool"], arguments["project"], arguments["task"]
    if tool not in {"claude", "codex"}:
        raise ValueError("coding tool must be claude or codex")
    if not isinstance(project, str) or not project.strip():
        raise ValueError("project is required")
    if not isinstance(task, str) or not task.strip():
        raise ValueError("task is required")
    return {
        "tool": tool,
        "project": project.strip()[:MAX_PROJECT_CHARS],
        "task": task.strip()[:MAX_TASK_CHARS],
    }


class AgentActionServer:
    """Daemon-owned Unix socket for exact, approval-bound agent actions."""

    def __init__(self, path: pathlib.Path | str, approvals, projects, sessions, *,
                 notifier_for_context: Callable[[str, str], Callable[[str], None]],
                 # This is the only approval left in an autonomous session, so
                 # the window has to survive the operator being away from Slack.
                 # It still denies on timeout.
                 timeout: float = 600.0):
        self.path = pathlib.Path(path)
        self.approvals = approvals
        self.projects = projects
        self.sessions = sessions
        self.notifier_for_context = notifier_for_context
        self.timeout = timeout
        self._socket: socket.socket | None = None
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()

    def start(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if self.path.exists():
            self.path.unlink()
        server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        server.bind(str(self.path))
        os.chmod(self.path, 0o600)
        server.listen()
        server.settimeout(0.1)
        self._socket = server
        self._thread = threading.Thread(target=self._serve, daemon=True)
        self._thread.start()

    def close(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=1)
        if self._socket:
            self._socket.close()
        self.path.unlink(missing_ok=True)

    def _serve(self) -> None:
        assert self._socket is not None
        while not self._stop.is_set():
            try:
                connection, _address = self._socket.accept()
            except TimeoutError:
                continue
            threading.Thread(target=self._handle, args=(connection,), daemon=True).start()

    def _handle(self, connection: socket.socket) -> None:
        with connection:
            try:
                payload = json.loads(connection.makefile("r", encoding="utf-8").readline())
                result = self._dispatch(payload)
                response = {"ok": True, "result": result}
            except (AgentActionError, OSError, ValueError, TypeError, KeyError, json.JSONDecodeError) as error:
                response = {"ok": False, "error": str(error) or "action denied"}
            try:
                connection.sendall(json.dumps(response, sort_keys=True).encode() + b"\n")
            except BrokenPipeError:
                pass

    def _dispatch(self, payload: object) -> dict[str, object]:
        if not isinstance(payload, dict) or set(payload) != {"action", "arguments", "channel_id", "thread_ts"}:
            raise AgentActionError("action request is malformed")
        if payload["action"] != "start_coding":
            raise AgentActionError("action is not available")
        channel_id, thread_ts = payload["channel_id"], payload["thread_ts"]
        if not isinstance(channel_id, str) or not channel_id or not isinstance(thread_ts, str) or not thread_ts:
            raise AgentActionError("action origin is incomplete")
        if not isinstance(payload["arguments"], dict):
            raise AgentActionError("action arguments are malformed")
        try:
            arguments = validate_start_coding(payload["arguments"])
            project = self.projects.select(arguments["project"])
        except (ValueError, ProjectQueryError) as error:
            raise AgentActionError(str(error)) from None

        summary = (
            f"Agent requests starting {arguments['tool']} in {project.name}: "
            f"{arguments['task']}"
        )
        notifier = self.notifier_for_context(channel_id, thread_ts)
        origin = (channel_id, thread_ts)
        if not self.approvals.request(
            summary, timeout=self.timeout, notifier=notifier, origin=origin,
        ):
            raise AgentActionError("operator denied the action")
        try:
            session = self.sessions.launch(
                arguments["tool"],
                cwd=project.path,
                prompt=arguments["task"],
                channel_id=channel_id,
                thread_ts=thread_ts,
            )
        except (GatewayDisarmedError, RuntimeError, ValueError) as error:
            raise AgentActionError(str(error)) from None
        return {
            "status": "started",
            "session_id": session.id,
            "tool": session.tool,
            "cwd": session.cwd,
        }


def request_action(path: pathlib.Path | str, action: str, arguments: dict[str, object], *,
                   channel_id: str, thread_ts: str, connect_timeout: float = 1.0) -> dict[str, object]:
    """MCP-facing client. Missing daemon, malformed replies, and denials fail closed."""
    if not all(isinstance(value, str) and value for value in (action, channel_id, thread_ts)):
        raise AgentActionError("action identity is incomplete")
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
            client.settimeout(connect_timeout)
            client.connect(str(path))
            client.settimeout(None)
            client.sendall(json.dumps({
                "action": action,
                "arguments": arguments,
                "channel_id": channel_id,
                "thread_ts": thread_ts,
            }, sort_keys=True).encode() + b"\n")
            response = json.loads(client.makefile("r", encoding="utf-8").readline())
    except (OSError, ValueError, TypeError, json.JSONDecodeError, AttributeError) as error:
        raise AgentActionError("agent action service is unavailable") from error
    if not isinstance(response, dict) or response.get("ok") is not True or not isinstance(response.get("result"), dict):
        message = response.get("error") if isinstance(response, dict) else None
        raise AgentActionError(str(message or "action denied"))
    return response["result"]
