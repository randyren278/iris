"""Session commands independent of Slack transport and approval plumbing."""
from __future__ import annotations

import signal


class GatewayDisarmedError(RuntimeError):
    pass


class SessionController:
    def __init__(self, registry, launcher, *, terminator=None, transport=None):
        self.registry = registry
        self.launcher = launcher
        self._terminator = terminator or _terminate
        self.transport = transport
        self.disarmed = False

    def launch(self, tool, *, cwd, prompt):
        if self.disarmed:
            raise GatewayDisarmedError("gateway is disarmed; re-arm from the terminal")
        process = self.launcher.launch(tool, cwd=cwd, prompt=prompt)
        session = self.registry.add(tool=tool, pid=process.pid, cwd=cwd, prompt=prompt)
        if self.transport:
            self.transport.register(session, process)
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
        return len(sessions)

    def rearm_from_terminal(self) -> None:
        self.disarmed = False

    def steer(self, session_id: int, prompt: str) -> bool:
        return bool(self.transport and self.transport.send(session_id, prompt))

    def bind_thread(self, session_id: int, channel_id: str, thread_ts: str) -> None:
        if self.transport:
            self.transport.bind_thread(session_id, channel_id, thread_ts)


def _terminate(pid: int) -> None:
    import os
    os.kill(pid, signal.SIGTERM)
