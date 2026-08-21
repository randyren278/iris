import threading
from types import SimpleNamespace

from iris.agent_actions import AgentActionServer, request_action
from iris.approvals import ApprovalQueue
from iris.main import route_message
from iris.projects import ProjectCatalog
from iris.router import CommandRouter
from iris.slack import SlackGateway
from tests.slack_fakes import RecordingSlackClient
from tests.waiting import wait_until


class RecordingSessions:
    def __init__(self):
        self.calls = []

    def launch(self, tool, **kwargs):
        self.calls.append((tool, kwargs))
        return SimpleNamespace(id=3, tool=tool, cwd=str(kwargs["cwd"]))

    def sessions(self):
        return ()

    def stop(self):
        return 0

    def kill(self, _index):
        return False

    def steer(self, _index, _text):
        return False


class ActionConversation:
    def __init__(self, socket_path):
        self.socket_path = socket_path

    def reply(self, message):
        result = request_action(
            self.socket_path,
            "start_coding",
            {"tool": "claude", "project": "iris", "task": "fix the failing tests"},
            channel_id=message.channel_id,
            thread_ts=message.reply_thread_ts,
        )
        return f"Started {result['tool']} session {result['session_id']}."


def envelope(event_id, text, *, ts, thread_ts=None):
    event = {
        "type": "message",
        "user": "U-operator",
        "channel": "D-1",
        "channel_type": "im",
        "text": text,
        "ts": ts,
    }
    if thread_ts is not None:
        event["thread_ts"] = thread_ts
    return {"type": "events_api", "event_id": event_id, "event": event}


def test_plain_english_can_cross_into_exactly_approved_coding_action(tmp_path, socket_dir):
    project = tmp_path / "Iris"
    project.mkdir()
    client = RecordingSlackClient()
    approvals = ApprovalQueue(
        notifier=lambda _text: (_ for _ in ()).throw(RuntimeError("unbound approval"))
    )
    sessions = RecordingSessions()
    projects = ProjectCatalog.discover(tmp_path)

    def notifier_for_context(channel_id, thread_ts):
        return lambda text: client.post_message(channel_id=channel_id, thread_ts=thread_ts, text=text)

    action_server = AgentActionServer(
        socket_dir / "agent-action.sock",
        approvals,
        projects,
        sessions,
        notifier_for_context=notifier_for_context,
        timeout=1,
    )
    action_server.start()
    router = CommandRouter(projects, sessions, approvals)
    conversation = ActionConversation(action_server.path)
    gateway = SlackGateway(
        ["U-operator"],
        client,
        handler=lambda message: route_message(message, router, conversation),
    )

    first = threading.Thread(target=lambda: gateway.handle_envelope(
        envelope("Ev-1", "please fix Iris", ts="10.2")
    ))
    first.start()
    wait_until(approvals.pending, message="approvals never received a pending approval")

    assert sessions.calls == []
    assert client.messages[0]["thread_ts"] == "10.2"
    assert "Agent requests starting claude in Iris" in client.messages[0]["text"]

    assert gateway.handle_envelope(
        envelope("Ev-2", "y 1", ts="10.3", thread_ts="10.2")
    )
    first.join(1)
    action_server.close()

    assert sessions.calls == [("claude", {
        "cwd": project.resolve(),
        "prompt": "fix the failing tests",
        "channel_id": "D-1",
        "thread_ts": "10.2",
    })]
    assert any(message["text"] == "Approval 1 recorded." for message in client.messages)
    assert any(message["text"] == "Started claude session 3." and message["thread_ts"] == "10.2"
               for message in client.messages)
