from iris.slack import SlackGateway
from tests.slack_fakes import RecordingSlackClient


def test_non_allowlisted_slack_event_does_not_reach_command_handler():
    client = RecordingSlackClient()
    reached = []
    gateway = SlackGateway(["U-operator"], client, handler=lambda message: reached.append(message) or "bad")
    envelope = {"type": "events_api", "event_id": "Ev-1", "event": {
        "type": "message", "user": "U-stranger", "channel": "D-1", "channel_type": "im",
        "text": "stop", "ts": "1.1",
    }}

    assert gateway.handle_envelope(envelope) is False
    assert reached == []
    assert client.messages == []
