from iris.launcher import Launcher
from iris.registry import SessionRegistry
from iris.sessions import SessionController


class Process:
    pid = 8


def test_sessions_reports_registered_sessions(tmp_path):
    controller = SessionController(SessionRegistry(tmp_path / "sessions.json", alive=lambda _pid: True),
                                  Launcher(popen=lambda *_args, **_kwargs: Process()))
    controller.launch("codex", cwd=tmp_path, prompt="status")

    assert len(controller.sessions()) == 1
