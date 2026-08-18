import pytest

from iris.launcher import Launcher
from iris.registry import SessionRegistry
from iris.sessions import GatewayDisarmedError, SessionController


def test_disarmed_gateway_rejects_launches_until_terminal_rearm(tmp_path):
    controller = SessionController(SessionRegistry(tmp_path / "sessions.json", alive=lambda _pid: True),
                                  Launcher(popen=lambda *_args, **_kwargs: None))
    controller.stop()

    with pytest.raises(GatewayDisarmedError):
        controller.launch("claude", cwd=tmp_path, prompt="no")

    controller.rearm_from_terminal()
    assert controller.disarmed is False
