"""Bidirectional, line-oriented transport for live Claude coding sessions."""
from __future__ import annotations

import json
import threading
from collections import defaultdict


class SessionTransport:
    """Owns ephemeral process pipes; the durable registry retains only metadata."""

    def __init__(self, notifier, *, thread_factory=threading.Thread):
        self._notifier = notifier
        self._thread_factory = thread_factory
        self._processes = {}
        self._targets = {}
        self._pending = defaultdict(list)
        self._last_emitted = {}
        self._lock = threading.Lock()

    def register(self, session, process) -> None:
        if not getattr(process, "stdin", None) or not getattr(process, "stdout", None):
            return
        with self._lock:
            self._processes[session.id] = process
        worker = self._thread_factory(target=self._read, args=(session.id, process), daemon=True)
        worker.start()

    def bind_thread(self, session_id: int, channel_id: str, thread_ts: str) -> None:
        with self._lock:
            self._targets[session_id] = (channel_id, thread_ts)
            pending = self._pending.pop(session_id, [])
        for text in pending:
            self._notifier(channel_id, thread_ts, text)

    def send(self, session_id: int, prompt: str) -> bool:
        with self._lock:
            process = self._processes.get(session_id)
        if process is None or getattr(process, "poll", lambda: None)() is not None:
            return False
        try:
            process.stdin.write(json.dumps({"type": "user", "message": {
                "role": "user", "content": prompt,
            }}) + "\n")
            process.stdin.flush()
            return True
        except (BrokenPipeError, OSError):
            return False

    def remove(self, session_id: int) -> None:
        with self._lock:
            self._processes.pop(session_id, None)
            self._targets.pop(session_id, None)
            self._pending.pop(session_id, None)
            self._last_emitted.pop(session_id, None)

    def _read(self, session_id: int, process) -> None:
        for line in process.stdout:
            text = _event_text(line)
            if text:
                self._emit(session_id, text)
        self._emit(session_id, "Session finished.")

    def _emit(self, session_id: int, text: str) -> None:
        with self._lock:
            if self._last_emitted.get(session_id) == text:
                return
            self._last_emitted[session_id] = text
            target = self._targets.get(session_id)
            if target is None:
                self._pending[session_id].append(text)
                return
        self._notifier(*target, text)


def _event_text(line: str) -> str | None:
    try:
        event = json.loads(line)
    except json.JSONDecodeError:
        return line.strip() or None
    if event.get("type") == "result" and isinstance(event.get("result"), str):
        return event["result"].strip() or None
    message = event.get("message")
    if isinstance(message, dict):
        content = message.get("content")
        if isinstance(content, str):
            return content.strip() or None
        if isinstance(content, list):
            text = "\n".join(item.get("text", "") for item in content
                             if isinstance(item, dict) and isinstance(item.get("text"), str))
            return text.strip() or None
    return None
