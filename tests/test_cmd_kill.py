from iris.launcher import Launcher
from iris.registry import SessionRegistry
from iris.sessions import SessionController


class Process:
    pid = 8


def test_kill_terminates_only_requested_session(tmp_path):
    terminated = []
    controller = SessionController(SessionRegistry(tmp_path / "sessions.json", alive=lambda _pid: True),
                                  Launcher(popen=lambda *_args, **_kwargs: Process()), terminator=terminated.append)
    session = controller.launch("codex", cwd=tmp_path, prompt="status")

    assert controller.kill(session.id) is True
    assert terminated == [8]
    assert controller.sessions() == ()
