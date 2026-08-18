from iris.launcher import Launcher
from iris.registry import SessionRegistry
from iris.sessions import SessionController


class Process:
    def __init__(self, pid):
        self.pid = pid


def test_stop_terminates_every_session_and_disarms(tmp_path):
    next_pid = iter([8, 9])
    terminated = []
    controller = SessionController(SessionRegistry(tmp_path / "sessions.json", alive=lambda _pid: True),
                                  Launcher(popen=lambda *_args, **_kwargs: Process(next(next_pid))),
                                  terminator=terminated.append)
    controller.launch("claude", cwd=tmp_path, prompt="one")
    controller.launch("codex", cwd=tmp_path, prompt="two")

    assert controller.stop() == 2
    assert terminated == [8, 9]
    assert controller.disarmed is True
