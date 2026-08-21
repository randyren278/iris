"""Deterministic command routing between Slack transport and local controls."""
from __future__ import annotations

from iris.grammar import IndexedCommand, Simple, TextCommand, parse
from iris.projects import ProjectQueryError
from iris.memory import MemoryPolicyError
from iris.sessions import GatewayDisarmedError


class CommandRouter:
    def __init__(self, catalog, sessions, approvals, *, memory=None):
        self.catalog = catalog
        self.sessions = sessions
        self.approvals = approvals
        self.memory = memory
        self._active_projects = {}

    def handle(self, message) -> str:
        command = parse(message.text)
        if command is None:
            return "I didn't recognize that. Try `projects`, `cd <project>`, `claude <task>`, or `codex <task>`."
        channel_id = message.channel_id
        reply_thread_ts = getattr(message, "reply_thread_ts", None)
        if isinstance(command, Simple):
            return self._simple(command, channel_id, reply_thread_ts)
        if isinstance(command, TextCommand):
            return self._text(
                command,
                channel_id,
                reply_thread_ts,
                getattr(message, "thread_ts", None),
            )
        return self._indexed(command, channel_id, reply_thread_ts)

    @staticmethod
    def _origin(channel_id, thread_ts):
        return (channel_id, thread_ts) if channel_id and thread_ts else None

    def _simple(self, command, channel_id, thread_ts=None):
        if command.name in {"ls", "projects"}:
            names = [project.name for project in self.catalog.projects]
            return "Projects: " + (", ".join(names) if names else "none found")
        if command.name == "memories":
            if self.memory is None:
                return "Memory is not configured."
            records = self.memory.retrieve()
            return "Memories: " + ("; ".join(f"{item.id}: {item.claim}" for item in records) if records else "none")
        if command.name == "sessions":
            sessions = self.sessions.sessions()
            return "Sessions: " + (", ".join(f"{item.id} {item.tool} {item.cwd}" for item in sessions)
                                   if sessions else "none")
        if command.name == "stop":
            return f"Stopped {self.sessions.stop()} session(s); gateway is disarmed. Re-arm from the terminal."
        if command.name in {"y", "n"}:
            return ("Approval recorded." if self.approvals.resolve(
                command.name == "y", origin=self._origin(channel_id, thread_ts)
            ) else "No pending approval in this thread.")
        raise AssertionError(f"unsupported simple command {command.name}")

    def _text(self, command, channel_id, thread_ts, scope_thread_ts=None):
        if command.name == "remember":
            if self.memory is None:
                return "Memory is not configured."
            try:
                record = self.memory.remember(command.text, source_ref=f"slack:{channel_id}:{thread_ts}")
            except MemoryPolicyError as error:
                return f"Memory update failed: {error}."
            return f"Remembered memory {record.id}."
        if command.name == "forget":
            if self.memory is None:
                return "Memory is not configured."
            try:
                self.memory.forget(command.text)
            except MemoryPolicyError as error:
                return f"Memory update failed: {error}."
            return f"Forgot memory {command.text}."
        if command.name == "correct":
            if self.memory is None:
                return "Memory is not configured."
            record_id, separator, claim = command.text.partition(" ")
            if not separator:
                return "Use `correct <memory-id> <replacement claim>`."
            try:
                record = self.memory.correct(record_id, claim, source_ref=f"slack:{channel_id}:{thread_ts}")
            except MemoryPolicyError as error:
                return f"Memory update failed: {error}."
            return f"Corrected memory {record_id} with {record.id}."

        scope_key = (channel_id, scope_thread_ts)
        default_key = (channel_id, None)
        if command.name == "cd":
            try:
                project = self.catalog.select(command.text)
            except ProjectQueryError as error:
                return f"Project selection failed: {error}."
            self._active_projects[scope_key] = project.path
            return f"Active project: {project.name}"

        project = self._active_projects.get(scope_key)
        if project is None and scope_thread_ts is not None:
            project = self._active_projects.get(default_key)
        if project is None:
            return "Select a project first with `cd <project>`."
        try:
            session = self.sessions.launch(
                command.name,
                cwd=project,
                prompt=command.text,
                channel_id=channel_id,
                thread_ts=thread_ts,
            )
        except GatewayDisarmedError as error:
            return str(error)
        except RuntimeError as error:
            return f"Could not start session: {error}."
        return f"Started {session.tool} session {session.id} in {session.cwd}."

    def _indexed(self, command, channel_id=None, thread_ts=None):
        if command.name == "approval":
            approved = command.text == "y"
            return (f"Approval {command.index} recorded."
                    if self.approvals.resolve(
                        approved, index=command.index, origin=self._origin(channel_id, thread_ts)
                    ) else f"No pending approval {command.index} in this thread.")
        if command.name == "kill":
            return f"Killed session {command.index}." if self.sessions.kill(command.index) else "No such session."
        if command.name == "session_message":
            return (f"Delivered to session {command.index}." if self.sessions.steer(command.index, command.text)
                    else "No live session transport for that session.")
        raise AssertionError(f"unsupported indexed command {command.name}")
