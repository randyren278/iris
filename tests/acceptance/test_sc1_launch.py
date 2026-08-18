from types import SimpleNamespace

from iris.approvals import ApprovalQueue
from iris.launcher import Launcher
from iris.projects import ProjectCatalog
from iris.registry import SessionRegistry
from iris.router import CommandRouter
from iris.sessions import SessionController
from iris.slack import SlackGateway
from tests.slack_fakes import RecordingSlackClient


class Process:
    pid = 123


def envelope(event_id, text):
    return {"type": "events_api", "event_id": event_id, "event": {
        "type": "message", "user": "U-operator", "channel": "D-1", "channel_type": "im",
        "text": text, "ts": event_id,
    }}


def test_slack_cd_then_claude_launches_in_same_dm_thread(tmp_path):
    project = tmp_path / "Iris"
    project.mkdir()
    router = CommandRouter(
        ProjectCatalog.discover(tmp_path),
        SessionController(SessionRegistry(tmp_path / "sessions.json", alive=lambda _pid: True),
                          Launcher(popen=lambda *_args, **_kwargs: Process())),
        ApprovalQueue(notifier=lambda _message: None),
    )
    client = RecordingSlackClient()
    gateway = SlackGateway(["U-operator"], client, handler=router.handle)

    gateway.handle_envelope(envelope("1.1", "cd iris"))
    gateway.handle_envelope(envelope("1.2", "claude fix the tests"))

    assert client.messages[0]["thread_ts"] == "1.1"
    assert client.messages[1]["thread_ts"] == "1.2"
    assert client.messages[1]["text"].startswith("Started claude session 1")
