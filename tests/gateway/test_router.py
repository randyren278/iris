from types import SimpleNamespace

from iris.approvals import ApprovalQueue
from iris.launcher import Launcher
from iris.memory import MemoryPolicyError, MemoryStore
from iris.projects import ProjectCatalog
from iris.registry import SessionRegistry
from iris.router import CommandRouter
from iris.sessions import GatewayDisarmedError, SessionController


class Process:
    pid = 77


class FakeSessions:
    def __init__(self):
        self.items = []
        self.launch_error = None
        self.launches = []
        self.kills = {}
        self.steers = {}
        self.stopped = 0

    def sessions(self):
        return tuple(self.items)

    def launch(self, tool, **kwargs):
        if self.launch_error:
            raise self.launch_error
        self.launches.append((tool, kwargs))
        return SimpleNamespace(id=len(self.launches), tool=tool, cwd=str(kwargs["cwd"]))

    def kill(self, index):
        return self.kills.get(index, False)

    def steer(self, index, text):
        return self.steers.get((index, text), False)

    def stop(self):
        return self.stopped


class FakeApprovals:
    def __init__(self):
        self.results = {}
        self.calls = []

    def resolve(self, approved, *, index=None):
        self.calls.append((approved, index))
        return self.results.get(index, self.results.get(None, False))


class BrokenMemory:
    def retrieve(self):
        return ()

    def remember(self, *_args, **_kwargs):
        raise MemoryPolicyError("remember blocked")

    def forget(self, *_args, **_kwargs):
        raise MemoryPolicyError("forget blocked")

    def correct(self, *_args, **_kwargs):
        raise MemoryPolicyError("correct blocked")


def real_router(tmp_path):
    (tmp_path / "Iris").mkdir()
    return CommandRouter(
        ProjectCatalog.discover(tmp_path),
        SessionController(SessionRegistry(tmp_path / "sessions.json", alive=lambda _pid: True),
                          Launcher(popen=lambda *_args, **_kwargs: Process())),
        ApprovalQueue(notifier=lambda _message: None),
    )


def message(text, *, channel="D-1", ts="1.0", thread_ts=None):
    return SimpleNamespace(
        text=text,
        channel_id=channel,
        reply_thread_ts=thread_ts or ts,
        thread_ts=thread_ts,
    )


def make_router(tmp_path, *, sessions=None, approvals=None, memory=None, projects=("Iris",)):
    for name in projects:
        (tmp_path / name).mkdir(exist_ok=True)
    return CommandRouter(
        ProjectCatalog.discover(tmp_path),
        sessions or FakeSessions(),
        approvals or FakeApprovals(),
        memory=memory,
    )


def test_router_selects_project_then_launches_session(tmp_path):
    commands = real_router(tmp_path)
    assert commands.handle(message("cd iris")) == "Active project: Iris"
    assert commands.handle(message("claude fix tests")).startswith("Started claude session 1")


def test_router_keeps_unparsed_input_inert(tmp_path):
    assert "didn't recognize" in real_router(tmp_path).handle(message("please destroy files"))


def test_router_lists_projects_and_empty_catalog(tmp_path):
    commands = make_router(tmp_path, projects=("Iris", "Beta"))
    assert commands.handle(message("projects")) == "Projects: Beta, Iris"
    assert commands.handle(message("ls")) == "Projects: Beta, Iris"

    empty = CommandRouter(ProjectCatalog.discover(tmp_path / "missing"), FakeSessions(), FakeApprovals())
    assert empty.handle(message("projects")) == "Projects: none found"


def test_router_lists_sessions_and_stop_state(tmp_path):
    sessions = FakeSessions()
    sessions.items = [SimpleNamespace(id=4, tool="claude", cwd="/work/iris")]
    sessions.stopped = 2
    commands = make_router(tmp_path, sessions=sessions)
    assert commands.handle(message("sessions")) == "Sessions: 4 claude /work/iris"
    assert commands.handle(message("stop")) == "Stopped 2 session(s); gateway is disarmed. Re-arm from the terminal."

    sessions.items = []
    assert commands.handle(message("sessions")) == "Sessions: none"


def test_router_bare_and_indexed_approval_resolution(tmp_path):
    approvals = FakeApprovals()
    approvals.results[None] = True
    approvals.results[7] = True
    commands = make_router(tmp_path, approvals=approvals)

    assert commands.handle(message("y")) == "Approval recorded."
    approvals.results[None] = False
    assert commands.handle(message("n")) == "No pending approval."
    assert commands.handle(message("y 7")) == "Approval 7 recorded."
    assert commands.handle(message("n 8")) == "No pending approval 8."
    assert approvals.calls == [(True, None), (False, None), (True, 7), (False, 8)]


def test_router_memory_requires_configuration_and_preserves_provenance(tmp_path):
    commands = make_router(tmp_path)
    for text in ("memories", "remember hello", "forget m1", "correct m1 replacement"):
        assert "Memory is not configured" in commands.handle(message(text))

    memory = MemoryStore(tmp_path / "memory.json", ids=iter(("m1", "m2")).__next__)
    commands = make_router(tmp_path, memory=memory)
    assert commands.handle(message("remember Prefer terse output", ts="2.1")) == "Remembered memory m1."
    assert "m1: Prefer terse output" in commands.handle(message("memories"))
    assert commands.handle(message("correct m1 Prefer concise output", ts="2.2")) == "Corrected memory m1 with m2."
    assert commands.handle(message("forget m2")) == "Forgot memory m2."
    assert commands.handle(message("memories")) == "Memories: none"


def test_router_memory_policy_errors_are_safe_messages(tmp_path):
    commands = make_router(tmp_path, memory=BrokenMemory())
    assert commands.handle(message("remember x")) == "Memory update failed: remember blocked."
    assert commands.handle(message("forget x")) == "Memory update failed: forget blocked."
    assert commands.handle(message("correct x y")) == "Memory update failed: correct blocked."
    assert commands.handle(message("correct x")) == "Use `correct <memory-id> <replacement claim>`."


def test_router_project_selection_failure_and_missing_active_project(tmp_path):
    commands = make_router(tmp_path, projects=("Alpha", "Alpine"))
    assert commands.handle(message("cd does-not-exist")).startswith("Project selection failed:")
    assert commands.handle(message("claude work")) == "Select a project first with `cd <project>`."


def test_router_thread_override_falls_back_to_channel_default(tmp_path):
    sessions = FakeSessions()
    commands = make_router(tmp_path, sessions=sessions, projects=("Alpha", "Beta"))
    assert commands.handle(message("cd alpha", ts="1.0")) == "Active project: Alpha"
    commands.handle(message("claude inherited", ts="2.1", thread_ts="2.0"))
    assert sessions.launches[-1][1]["cwd"] == (tmp_path / "Alpha").resolve()

    assert commands.handle(message("cd beta", ts="2.2", thread_ts="2.0")) == "Active project: Beta"
    commands.handle(message("codex thread", ts="2.3", thread_ts="2.0"))
    assert sessions.launches[-1][1]["cwd"] == (tmp_path / "Beta").resolve()
    assert sessions.launches[-1][1]["channel_id"] == "D-1"
    assert sessions.launches[-1][1]["thread_ts"] == "2.0"


def test_router_surfaces_disarmed_and_launch_runtime_failures(tmp_path):
    sessions = FakeSessions()
    commands = make_router(tmp_path, sessions=sessions)
    commands.handle(message("cd iris"))

    sessions.launch_error = GatewayDisarmedError("gateway is disarmed; re-arm from the terminal")
    assert commands.handle(message("claude x")) == "gateway is disarmed; re-arm from the terminal"

    sessions.launch_error = RuntimeError("transport failed")
    assert commands.handle(message("claude x")) == "Could not start session: transport failed."


def test_router_kill_and_steer_commands_cover_success_and_failure(tmp_path):
    sessions = FakeSessions()
    sessions.kills[3] = True
    sessions.steers[(4, "continue")] = True
    commands = make_router(tmp_path, sessions=sessions)

    assert commands.handle(message("kill 3")) == "Killed session 3."
    assert commands.handle(message("kill 9")) == "No such session."
    assert commands.handle(message("@4 continue")) == "Delivered to session 4."
    assert commands.handle(message("@5 nope")) == "No live session transport for that session."
