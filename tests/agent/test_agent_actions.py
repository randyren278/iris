import threading
import time
from types import SimpleNamespace

import pytest

from iris.agent_actions import AgentActionError, AgentActionServer, request_action, validate_start_coding
from iris.approvals import ApprovalQueue
from iris.projects import ProjectCatalog


class RecordingSessions:
    def __init__(self):
        self.calls = []

    def launch(self, tool, **kwargs):
        self.calls.append((tool, kwargs))
        return SimpleNamespace(id=9, tool=tool, cwd=str(kwargs["cwd"]))


def _server(tmp_path):
    project = tmp_path / "Iris"
    project.mkdir()
    notices = []
    queue = ApprovalQueue(notifier=lambda _message: (_ for _ in ()).throw(RuntimeError("unbound")))
    sessions = RecordingSessions()
    server = AgentActionServer(
        tmp_path / "agent-action.sock",
        queue,
        ProjectCatalog.discover(tmp_path),
        sessions,
        notifier_for_context=lambda channel, thread: lambda text: notices.append((channel, thread, text)),
        timeout=1,
    )
    server.start()
    return server, queue, sessions, notices, project


def test_start_coding_action_waits_for_exact_origin_approval(tmp_path):
    server, queue, sessions, notices, project = _server(tmp_path)
    outcome = []
    worker = threading.Thread(target=lambda: outcome.append(request_action(
        server.path,
        "start_coding",
        {"tool": "claude", "project": "iris", "task": "repair the failing tests"},
        channel_id="D-1",
        thread_ts="11.2",
    )))
    worker.start()
    while not queue.pending():
        time.sleep(0.005)

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


def test_denied_agent_action_never_launches_session(tmp_path):
    server, queue, sessions, _notices, _project = _server(tmp_path)
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
    while not queue.pending():
        time.sleep(0.005)
    assert queue.resolve(False, index=1, origin=("D-1", "12.1"))
    worker.join(1)
    server.close()

    assert errors == ["operator denied the action"]
    assert sessions.calls == []


def test_action_schema_rejects_paths_and_unknown_tools():
    with pytest.raises(ValueError):
        validate_start_coding({"tool": "bash", "project": "iris", "task": "x"})
    with pytest.raises(ValueError):
        validate_start_coding({"tool": "claude", "project": "../outside", "task": "x", "path": "/tmp"})
