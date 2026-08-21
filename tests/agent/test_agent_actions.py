import os
import socket
import threading
import time
from types import SimpleNamespace

import pytest

from iris.agent_actions import AgentActionError, AgentActionServer, request_action, validate_start_coding
from iris.approvals import ApprovalQueue
from iris.projects import ProjectCatalog
from iris.sessions import GatewayDisarmedError
from tests.waiting import wait_until


class RecordingSessions:
    def __init__(self):
        self.calls = []
        self.error = None

    def launch(self, tool, **kwargs):
        if self.error:
            raise self.error
        self.calls.append((tool, kwargs))
        return SimpleNamespace(id=9, tool=tool, cwd=str(kwargs["cwd"]))


def _server(tmp_path, socket_dir):
    project = tmp_path / "Iris"
    project.mkdir(exist_ok=True)
    notices = []
    queue = ApprovalQueue(notifier=lambda _message: (_ for _ in ()).throw(RuntimeError("unbound")))
    sessions = RecordingSessions()
    server = AgentActionServer(
        socket_dir / "agent-action.sock",
        queue,
        ProjectCatalog.discover(tmp_path),
        sessions,
        notifier_for_context=lambda channel, thread: lambda text: notices.append((channel, thread, text)),
        timeout=1,
    )
    server.start()
    return server, queue, sessions, notices, project


def test_start_coding_action_waits_for_exact_origin_approval(tmp_path, socket_dir):
    server, queue, sessions, notices, project = _server(tmp_path, socket_dir)
    outcome = []
    worker = threading.Thread(target=lambda: outcome.append(request_action(
        server.path,
        "start_coding",
        {"tool": "claude", "project": "iris", "task": "repair the failing tests"},
        channel_id="D-1",
        thread_ts="11.2",
    )))
    worker.start()
    wait_until(queue.pending, message="queue never received a pending approval")

    assert sessions.calls == []
    assert notices and notices[0][:2] == ("D-1", "11.2")
    assert "repair the failing tests" in notices[0][2]
    assert not queue.resolve(True, index=1, origin=("D-1", "different-thread"))
    assert sessions.calls == []
    assert queue.resolve(True, index=1, origin=("D-1", "11.2"))
    worker.join(1)
    server.close()

    assert outcome == [{"status": "started", "session_id": 9, "tool": "claude", "cwd": str(project.resolve())}]
    assert sessions.calls == [("claude", {
        "cwd": project.resolve(),
        "prompt": "repair the failing tests",
        "channel_id": "D-1",
        "thread_ts": "11.2",
    })]


def test_denied_agent_action_never_launches_session(tmp_path, socket_dir):
    server, queue, sessions, _notices, _project = _server(tmp_path, socket_dir)
    errors = []

    def run():
        try:
            request_action(
                server.path,
                "start_coding",
                {"tool": "codex", "project": "iris", "task": "change production code"},
                channel_id="D-1",
                thread_ts="12.1",
            )
        except AgentActionError as error:
            errors.append(str(error))

    worker = threading.Thread(target=run)
    worker.start()
    wait_until(queue.pending, message="queue never received a pending approval")
    assert queue.resolve(False, index=1, origin=("D-1", "12.1"))
    worker.join(1)
    server.close()

    assert errors == ["operator denied the action"]
    assert sessions.calls == []


def test_action_schema_is_exact_nonempty_and_bounded():
    assert validate_start_coding({"tool": "claude", "project": "  Iris  ", "task": "  fix  "}) == {
        "tool": "claude", "project": "Iris", "task": "fix"
    }
    bounded = validate_start_coding({"tool": "codex", "project": "p" * 300, "task": "t" * 5000})
    assert len(bounded["project"]) == 200
    assert len(bounded["task"]) == 4000

    invalid = (
        {"tool": "bash", "project": "iris", "task": "x"},
        {"tool": "claude", "project": "../outside", "task": "x", "path": "/tmp"},
        {"tool": "claude", "project": "", "task": "x"},
        {"tool": "claude", "project": 3, "task": "x"},
        {"tool": "claude", "project": "iris", "task": ""},
        {"tool": "claude", "project": "iris", "task": 3},
    )
    for arguments in invalid:
        with pytest.raises(ValueError):
            validate_start_coding(arguments)


def test_action_socket_replaces_stale_path_and_is_owner_only(tmp_path, socket_dir):
    path = socket_dir / "agent-action.sock"
    path.write_text("stale")
    project = tmp_path / "Iris"
    project.mkdir()
    server = AgentActionServer(
        path,
        ApprovalQueue(notifier=lambda _message: None),
        ProjectCatalog.discover(tmp_path),
        RecordingSessions(),
        notifier_for_context=lambda _channel, _thread: lambda _text: None,
    )
    server.start()
    try:
        assert path.is_socket()
        assert path.stat().st_mode & 0o777 == 0o600
    finally:
        server.close()
    assert not path.exists()
    server.close()  # idempotent after a completed close


def make_direct_server(tmp_path, *, sessions=None, approval=True):
    project = tmp_path / "Iris"
    project.mkdir(exist_ok=True)

    class Approvals:
        def request(self, summary, *, timeout, notifier, origin=None):
            assert "Iris" in summary
            assert timeout == 120.0
            assert callable(notifier)
            assert origin == ("D1", "1.0")
            return approval

    return AgentActionServer(
        tmp_path / "unused.sock",
        Approvals(),
        ProjectCatalog.discover(tmp_path),
        sessions or RecordingSessions(),
        notifier_for_context=lambda _channel, _thread: lambda _text: None,
    )


def test_direct_dispatch_rejects_malformed_unknown_origin_and_project(tmp_path):
    server = make_direct_server(tmp_path)
    malformed = (
        None,
        {},
        {"action": "start_coding", "arguments": {}, "channel_id": "D1"},
    )
    for payload in malformed:
        with pytest.raises(AgentActionError, match="malformed"):
            server._dispatch(payload)

    with pytest.raises(AgentActionError, match="not available"):
        server._dispatch({"action": "delete", "arguments": {}, "channel_id": "D1", "thread_ts": "1.0"})
    with pytest.raises(AgentActionError, match="origin is incomplete"):
        server._dispatch({"action": "start_coding", "arguments": {}, "channel_id": "", "thread_ts": "1.0"})
    with pytest.raises(AgentActionError, match="arguments are malformed"):
        server._dispatch({"action": "start_coding", "arguments": [], "channel_id": "D1", "thread_ts": "1.0"})
    with pytest.raises(AgentActionError):
        server._dispatch({"action": "start_coding", "arguments": {
            "tool": "claude", "project": "missing", "task": "x"
        }, "channel_id": "D1", "thread_ts": "1.0"})


def test_direct_dispatch_wraps_session_launch_failures(tmp_path):
    for error in (GatewayDisarmedError("disarmed"), RuntimeError("transport"), ValueError("invalid")):
        sessions = RecordingSessions()
        sessions.error = error
        server = make_direct_server(tmp_path, sessions=sessions)
        with pytest.raises(AgentActionError, match=str(error)):
            server._dispatch({"action": "start_coding", "arguments": {
                "tool": "claude", "project": "iris", "task": "x"
            }, "channel_id": "D1", "thread_ts": "1.0"})


def test_direct_dispatch_denial_never_calls_session(tmp_path):
    sessions = RecordingSessions()
    server = make_direct_server(tmp_path, sessions=sessions, approval=False)
    with pytest.raises(AgentActionError, match="operator denied"):
        server._dispatch({"action": "start_coding", "arguments": {
            "tool": "claude", "project": "iris", "task": "x"
        }, "channel_id": "D1", "thread_ts": "1.0"})
    assert sessions.calls == []


def test_request_action_rejects_incomplete_identity_and_unavailable_daemon(tmp_path):
    with pytest.raises(AgentActionError, match="identity is incomplete"):
        request_action(tmp_path / "missing.sock", "", {}, channel_id="D1", thread_ts="1.0")
    with pytest.raises(AgentActionError, match="identity is incomplete"):
        request_action(tmp_path / "missing.sock", "start_coding", {}, channel_id="", thread_ts="1.0")
    with pytest.raises(AgentActionError, match="service is unavailable"):
        request_action(tmp_path / "missing.sock", "start_coding", {}, channel_id="D1", thread_ts="1.0")


def test_request_action_fails_closed_on_invalid_and_denied_server_reply(tmp_path, socket_dir):
    def one_reply(raw):
        path = socket_dir / f"reply-{time.time_ns()}.sock"
        ready = threading.Event()

        def serve():
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as listener:
                listener.bind(str(path))
                listener.listen(1)
                ready.set()
                connection, _ = listener.accept()
                with connection:
                    connection.makefile("r", encoding="utf-8").readline()
                    connection.sendall(raw + b"\n")

        thread = threading.Thread(target=serve)
        thread.start()
        ready.wait(1)
        return path, thread

    path, thread = one_reply(b"not-json")
    with pytest.raises(AgentActionError, match="service is unavailable"):
        request_action(path, "start_coding", {}, channel_id="D1", thread_ts="1.0")
    thread.join(1)

    path, thread = one_reply(b'{"ok":false,"error":"denied by policy"}')
    with pytest.raises(AgentActionError, match="denied by policy"):
        request_action(path, "start_coding", {}, channel_id="D1", thread_ts="1.0")
    thread.join(1)
