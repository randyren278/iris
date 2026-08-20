"""Session commands independent of Slack transport and approval plumbing."""
from __future__ import annotations

import os
import pathlib
import signal


class GatewayDisarmedError(RuntimeError):
    pass


class SessionController:
    def __init__(self, registry, launcher, *, terminator=None, transport=None, disarm_path=None):
        self.registry = registry
        self.launcher = launcher
        self._terminator = terminator or _terminate
        self.transport = transport
        self._disarm_path = pathlib.Path(disarm_path) if disarm_path else None
        self.disarmed = bool(self._disarm_path and self._disarm_path.exists())

    def launch(self, tool, *, cwd, prompt, channel_id=None, thread_ts=None):
        if self.disarmed:
            raise GatewayDisarmedError("gateway is disarmed; re-arm from the terminal")
        launch_kwargs = {"cwd": cwd, "prompt": prompt}
        if channel_id and thread_ts:
            launch_kwargs["approval_context"] = (channel_id, thread_ts)
        process = self.launcher.launch(tool, **launch_kwargs)
        session = self.registry.add(tool=tool, pid=process.pid, cwd=cwd, prompt=prompt)
        if self.transport:
            self.transport.register(session, process)
            if channel_id and thread_ts:
                self.transport.bind_thread(session.id, channel_id, thread_ts)
            if tool == "claude" and not self.transport.send(session.id, prompt):
                self.registry.remove(session.id)
                self._terminator(session.pid)
                self.transport.remove(session.id)
                raise RuntimeError("unable to deliver the initial prompt to the Claude session")
        return session

    def sessions(self):
        return self.registry.sessions()

    def kill(self, session_id: int) -> bool:
        session = self.registry.remove(session_id)
        if session is None:
            return False
        self._terminator(session.pid)
        if self.transport:
            self.transport.remove(session.id)
        return True

    def stop(self) -> int:
        sessions = self.registry.clear()
        for session in sessions:
            self._terminator(session.pid)
            if self.transport:
                self.transport.remove(session.id)
        self.disarmed = True
        if self._disarm_path:
            self._disarm_path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            self._disarm_path.write_text("disarmed\n")
            os.chmod(self._disarm_path, 0o600)
        return len(sessions)

    def rearm_from_terminal(self) -> None:
        if self._disarm_path:
            self._disarm_path.unlink(missing_ok=True)
        self.disarmed = False

    def steer(self, session_id: int, prompt: str) -> bool:
        return bool(self.transport and self.transport.send(session_id, prompt))

    def bind_thread(self, session_id: int, channel_id: str, thread_ts: str) -> None:
        if self.transport:
            self.transport.bind_thread(session_id, channel_id, thread_ts)


def _terminate(pid: int) -> None:
    os.kill(pid, signal.SIGTERM)
