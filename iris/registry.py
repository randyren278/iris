"""Restart-safe registry for locally launched coding sessions."""
from __future__ import annotations

import dataclasses
import json
import os
import pathlib
import time


@dataclasses.dataclass(frozen=True)
class Session:
    id: int
    tool: str
    pid: int
    cwd: str
    prompt: str
    started_at: float

    @classmethod
    def from_dict(cls, value: dict) -> Session:
        return cls(**value)


class SessionRegistry:
    def __init__(self, path: pathlib.Path | str, *, alive=None):
        self.path = pathlib.Path(path)
        self._alive = alive or _pid_is_alive
        self._sessions = self._load()

    def _load(self) -> dict[int, Session]:
        try:
            raw = json.loads(self.path.read_text())
            sessions = {int(value["id"]): Session.from_dict(value) for value in raw["sessions"]}
        except (FileNotFoundError, KeyError, TypeError, ValueError, json.JSONDecodeError):
            sessions = {}
        live = {session_id: session for session_id, session in sessions.items()
                if self._alive(session.pid)}
        if live != sessions:
            self._sessions = live
            self._save()
        return live

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(json.dumps({"sessions": [dataclasses.asdict(session)
                                                       for session in self.sessions()]}))
        temporary.replace(self.path)

    def sessions(self) -> tuple[Session, ...]:
        return tuple(self._sessions[session_id] for session_id in sorted(self._sessions))

    def add(self, *, tool: str, pid: int, cwd: pathlib.Path | str, prompt: str) -> Session:
        session_id = max(self._sessions, default=0) + 1
        session = Session(session_id, tool, pid, str(pathlib.Path(cwd).resolve()), prompt, time.time())
        self._sessions[session.id] = session
        self._save()
        return session

    def remove(self, session_id: int) -> Session | None:
        session = self._sessions.pop(session_id, None)
        if session is not None:
            self._save()
        return session

    def clear(self) -> tuple[Session, ...]:
        sessions = self.sessions()
        self._sessions.clear()
        self._save()
        return sessions


def _pid_is_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True
