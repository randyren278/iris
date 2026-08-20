"""Fail-closed tool-call approvals over a Unix-domain socket."""
from __future__ import annotations

import dataclasses
import json
import os
import pathlib
import socket
import threading
import time
from collections.abc import Callable


@dataclasses.dataclass
class PendingApproval:
    id: int
    summary: str
    decided: bool | None = None


class ApprovalQueue:
    def __init__(self, *, notifier: Callable[[str], None], clock=time.monotonic):
        self._notifier = notifier
        self._clock = clock
        self._condition = threading.Condition()
        self._pending: list[PendingApproval] = []
        self._next_id = 1

    def request(self, summary: str, *, timeout: float, notifier: Callable[[str], None] | None = None) -> bool:
        notify = notifier or self._notifier
        with self._condition:
            request = PendingApproval(self._next_id, summary)
            self._next_id += 1
            self._pending.append(request)
            deadline = self._clock() + timeout
        try:
            notify(self.render(request))
        except Exception:
            with self._condition:
                if request in self._pending:
                    self._pending.remove(request)
            return False
        with self._condition:
            while request.decided is None:
                remaining = deadline - self._clock()
                if remaining <= 0:
                    self._pending.remove(request)
                    timed_out = True
                    break
                self._condition.wait(remaining)
            else:
                timed_out = False
                self._pending.remove(request)
                decision = request.decided
        if timed_out:
            try:
                notify(f"Approval {request.id} timed out; denied.")
            except Exception:
                pass
            return False
        return decision is True

    def resolve(self, approved: bool, *, index: int | None = None) -> bool:
        with self._condition:
            if not self._pending:
                return False
            if index is None:
                request = self._pending[0]
            else:
                request = next((item for item in self._pending if item.id == index), None)
                if request is None:
                    return False
            request.decided = approved
            self._condition.notify_all()
            return True

    def pending(self) -> tuple[PendingApproval, ...]:
        with self._condition:
            return tuple(self._pending)

    @staticmethod
    def render(request: PendingApproval) -> str:
        return f"Approval {request.id}: {request.summary}\nReply y or n (or y {request.id}/n {request.id})."


class ApprovalServer:
    """One local Unix-socket endpoint used by coding-agent tool hooks."""

    def __init__(self, path: pathlib.Path | str, queue: ApprovalQueue, *, timeout: float = 120.0,
                 notifier_for_context: Callable[[str, str], Callable[[str], None]] | None = None):
        self.path = pathlib.Path(path)
        self.queue = queue
        self.timeout = timeout
        self._notifier_for_context = notifier_for_context
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
        if self.path.exists():
            self.path.unlink()

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
                summary = payload["summary"]
                if not isinstance(summary, str) or not summary:
                    raise ValueError("summary is required")
                channel_id = payload.get("channel_id")
                thread_ts = payload.get("thread_ts")
                if bool(channel_id) != bool(thread_ts):
                    raise ValueError("approval origin is incomplete")
                notifier = None
                if channel_id and thread_ts:
                    if (not isinstance(channel_id, str) or not isinstance(thread_ts, str)
                            or self._notifier_for_context is None):
                        raise ValueError("approval origin is unavailable")
                    notifier = self._notifier_for_context(channel_id, thread_ts)
                approved = self.queue.request(summary, timeout=self.timeout, notifier=notifier)
            except (OSError, ValueError, json.JSONDecodeError, KeyError, TypeError):
                approved = False
            try:
                connection.sendall(json.dumps({"approved": approved}).encode() + b"\n")
            except BrokenPipeError:
                pass


def request_approval(path: pathlib.Path | str, summary: str, *, channel_id: str | None = None,
                     thread_ts: str | None = None, connect_timeout: float = 1.0) -> bool:
    """Hook-facing client. Missing/unreachable daemon always denies."""
    if bool(channel_id) != bool(thread_ts):
        return False
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
            client.settimeout(connect_timeout)
            client.connect(str(path))
            # The short timeout protects only daemon reachability. A connected
            # hook may legitimately wait through the operator approval window.
            client.settimeout(None)
            payload = {"summary": summary}
            if channel_id and thread_ts:
                payload.update(channel_id=channel_id, thread_ts=thread_ts)
            client.sendall(json.dumps(payload).encode() + b"\n")
            response = json.loads(client.makefile("r", encoding="utf-8").readline())
            return response.get("approved") is True
    except (OSError, ValueError, json.JSONDecodeError, AttributeError):
        return False
