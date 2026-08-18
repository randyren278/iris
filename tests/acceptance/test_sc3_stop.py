import pytest

from iris.launcher import Launcher
from iris.registry import SessionRegistry
from iris.sessions import GatewayDisarmedError, SessionController


class Process:
    pid = 55


def test_stop_kills_and_disarms_all_sessions(tmp_path):
    stopped = []
    controller = SessionController(SessionRegistry(tmp_path / "sessions.json", alive=lambda _pid: True),
                                  Launcher(popen=lambda *_args, **_kwargs: Process()), terminator=stopped.append)
    controller.launch("claude", cwd=tmp_path, prompt="one")

    assert controller.stop() == 1
    assert stopped == [55]
    with pytest.raises(GatewayDisarmedError):
        controller.launch("codex", cwd=tmp_path, prompt="two")
