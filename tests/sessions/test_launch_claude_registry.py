from iris.launcher import Launcher
from iris.registry import SessionRegistry
from iris.sessions import SessionController


class Process:
    pid = 42


def test_claude_launch_is_recorded(tmp_path):
    controller = SessionController(
        SessionRegistry(tmp_path / "sessions.json", alive=lambda _pid: True),
        Launcher(popen=lambda *_args, **_kwargs: Process()),
    )

    session = controller.launch("claude", cwd=tmp_path, prompt="fix tests")

    assert controller.sessions() == (session,)
    assert session.tool == "claude"
