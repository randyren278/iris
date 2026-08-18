from types import SimpleNamespace

from iris.approvals import ApprovalQueue
from iris.launcher import Launcher
from iris.projects import ProjectCatalog
from iris.registry import SessionRegistry
from iris.router import CommandRouter
from iris.sessions import SessionController


class Process:
    pid = 77


def router(tmp_path):
    (tmp_path / "Iris").mkdir()
    return CommandRouter(
        ProjectCatalog.discover(tmp_path),
        SessionController(SessionRegistry(tmp_path / "sessions.json", alive=lambda _pid: True),
                          Launcher(popen=lambda *_args, **_kwargs: Process())),
        ApprovalQueue(notifier=lambda _message: None),
    )


def message(text):
    return SimpleNamespace(text=text, channel_id="D-1")


def test_router_selects_project_then_launches_session(tmp_path):
    commands = router(tmp_path)

    assert commands.handle(message("cd iris")) == "Active project: Iris"
    assert commands.handle(message("claude fix tests")).startswith("Started claude session 1")


def test_router_keeps_unparsed_input_inert(tmp_path):
    assert "didn't recognize" in router(tmp_path).handle(message("please destroy files"))
