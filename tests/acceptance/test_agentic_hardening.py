import threading
from types import SimpleNamespace

from iris.approvals import ApprovalQueue, ApprovalServer, request_approval
from iris.memory import MemoryStore
from iris.projects import ProjectCatalog
from iris.registry import SessionRegistry
from iris.router import CommandRouter
from iris.sessions import SessionController
from tests.waiting import wait_until


class FakeSessions:
    def __init__(self):
        self.launches = []

    def sessions(self):
        return ()

    def launch(self, tool, **kwargs):
        self.launches.append((tool, kwargs))
        return SimpleNamespace(id=len(self.launches), tool=tool, cwd=str(kwargs["cwd"]))

    def stop(self):
        return 0

    def kill(self, _index):
        return False

    def steer(self, _index, _text):
        return False


class FakeLauncher:
    def __init__(self):
        self.calls = []

    def launch(self, tool, **kwargs):
        self.calls.append((tool, kwargs))
        return SimpleNamespace(pid=91)


class FakeTransport:
    def __init__(self):
        self.events = []

    def register(self, session, _process):
        self.events.append(("register", session.id))

    def bind_thread(self, session_id, channel_id, thread_ts):
        self.events.append(("bind", session_id, channel_id, thread_ts))

    def send(self, session_id, prompt):
        self.events.append(("send", session_id, prompt))
        return True

    def remove(self, session_id):
        self.events.append(("remove", session_id))


def _message(text, *, ts="1.0", thread_ts=None):
    return SimpleNamespace(
        text=text,
        channel_id="D-1",
        reply_thread_ts=thread_ts or ts,
        thread_ts=thread_ts,
    )


def test_indexed_approval_command_resolves_the_requested_pending_action(tmp_path):
    queue = ApprovalQueue(notifier=lambda _message: None)
    router = CommandRouter(ProjectCatalog.discover(tmp_path), FakeSessions(), queue)
    results = {}

    first = threading.Thread(target=lambda: results.setdefault("first", queue.request("first", timeout=1)))
    first.start()
    wait_until(lambda: len(queue.pending()) >= 1, message="queue never reached 1 pending approval(s)")
    second = threading.Thread(target=lambda: results.setdefault("second", queue.request("second", timeout=1)))
    second.start()
    wait_until(lambda: len(queue.pending()) >= 2, message="queue never reached 2 pending approval(s)")

    assert router.handle(_message("y 2")) == "Approval 2 recorded."
    queue.resolve(False, index=1)
    first.join(1)
    second.join(1)

    assert results == {"first": False, "second": True}


def test_approval_socket_routes_and_resolves_only_in_exact_origin_thread(socket_dir):
    fallback = []
    routed = []
    queue = ApprovalQueue(notifier=fallback.append)

    def notifier_for_context(channel_id, thread_ts):
        return lambda text: routed.append((channel_id, thread_ts, text))

    server = ApprovalServer(
        socket_dir / "approval.sock",
        queue,
        timeout=1,
        notifier_for_context=notifier_for_context,
    )
    server.start()
    result = []
    worker = threading.Thread(target=lambda: result.append(request_approval(
        server.path,
        'Bash {"command":"pytest -q"}',
        channel_id="D-origin",
        thread_ts="42.1",
    )))
    worker.start()
    wait_until(queue.pending, message="queue never received a pending approval")

    assert not queue.resolve(True, index=1, origin=("D-origin", "WRONG"))
    assert worker.is_alive()
    assert queue.resolve(True, index=1, origin=("D-origin", "42.1"))
    worker.join(1)
    server.close()

    assert result == [True]
    assert fallback == []
    assert routed and routed[0][:2] == ("D-origin", "42.1")
    assert "pytest -q" in routed[0][2]


def test_session_binds_origin_before_initial_prompt_is_sent(tmp_path):
    launcher = FakeLauncher()
    transport = FakeTransport()
    controller = SessionController(
        SessionRegistry(tmp_path / "sessions.json", alive=lambda _pid: True),
        launcher,
        transport=transport,
    )

    controller.launch(
        "claude",
        cwd=tmp_path,
        prompt="fix it",
        channel_id="D-1",
        thread_ts="10.2",
    )

    assert launcher.calls[0][1]["approval_context"] == ("D-1", "10.2")
    assert transport.events == [
        ("register", 1),
        ("bind", 1, "D-1", "10.2"),
        ("send", 1, "fix it"),
    ]


def test_emergency_stop_persists_across_controller_restart(tmp_path):
    disarm_path = tmp_path / "disarmed"
    registry_path = tmp_path / "sessions.json"
    controller = SessionController(
        SessionRegistry(registry_path, alive=lambda _pid: True),
        FakeLauncher(),
        disarm_path=disarm_path,
    )

    controller.stop()
    assert disarm_path.exists()

    restarted = SessionController(
        SessionRegistry(registry_path, alive=lambda _pid: True),
        FakeLauncher(),
        disarm_path=disarm_path,
    )
    assert restarted.disarmed is True
    restarted.rearm_from_terminal()
    assert restarted.disarmed is False
    assert not disarm_path.exists()


def test_explicit_remember_command_is_retrievable_with_provenance(tmp_path):
    memory = MemoryStore(tmp_path / "memory.json", ids=lambda: "m1")
    router = CommandRouter(ProjectCatalog.discover(tmp_path), FakeSessions(),
                           ApprovalQueue(notifier=lambda _message: None), memory=memory)

    assert router.handle(_message("remember Prefer concise replies", ts="8.2")) == "Remembered memory m1."
    record = memory.retrieve("concise")[0]
    assert record.claim == "Prefer concise replies"
    assert record.source_ref == "slack:D-1:8.2"


def test_thread_project_override_does_not_mutate_default_dm_project(tmp_path):
    alpha = tmp_path / "Alpha"
    beta = tmp_path / "Beta"
    alpha.mkdir()
    beta.mkdir()
    sessions = FakeSessions()
    router = CommandRouter(ProjectCatalog.discover(tmp_path), sessions,
                           ApprovalQueue(notifier=lambda _message: None))

    assert router.handle(_message("cd alpha", ts="1.0")) == "Active project: Alpha"
    assert router.handle(_message("cd beta", ts="2.1", thread_ts="2.0")) == "Active project: Beta"
    router.handle(_message("claude default task", ts="3.0"))
    router.handle(_message("claude thread task", ts="2.2", thread_ts="2.0"))

    assert sessions.launches[0][1]["cwd"] == alpha.resolve()
    assert sessions.launches[1][1]["cwd"] == beta.resolve()
