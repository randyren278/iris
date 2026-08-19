from iris.slack import SlackGateway
from tests.slack_fakes import FakeEventSource, RecordingSlackClient


def dm_envelope(*, event_id="Ev-1", user_id="U-allowed", text="hello", ts="1.1", thread_ts=None):
    event = {"type": "message", "user": user_id, "channel": "D-1", "text": text,
             "ts": ts, "channel_type": "im"}
    if thread_ts:
        event["thread_ts"] = thread_ts
    return {"type": "events_api", "event_id": event_id, "event": event}


def test_allowlisted_dm_echoes_in_same_thread():
    client = RecordingSlackClient()
    source = FakeEventSource([dm_envelope(text="echo me", ts="10.2", thread_ts="10.1")])

    SlackGateway(["U-allowed"], client).run_forever(source)

    assert client.messages == [{"channel_id": "D-1", "text": "echo me", "thread_ts": "10.1"}]


def test_root_dm_reply_uses_its_message_timestamp_as_thread():
    client = RecordingSlackClient()

    SlackGateway(["U-allowed"], client).handle_envelope(dm_envelope(ts="10.2"))

    assert client.messages[0]["thread_ts"] == "10.2"


def test_transport_uses_configured_command_handler_response():
    client = RecordingSlackClient()
    gateway = SlackGateway(["U-allowed"], client, handler=lambda _message: "routed reply")

    gateway.handle_envelope(dm_envelope())

    assert client.messages[0]["text"] == "routed reply"


def test_transport_splits_long_handler_replies_in_the_origin_thread():
    client = RecordingSlackClient()
    gateway = SlackGateway(["U-allowed"], client, handler=lambda _message: "word " * 700,
                           splitter=lambda _text: ("first", "second"))
    gateway.handle_envelope(dm_envelope())

    assert [item["text"] for item in client.messages] == ["first", "second"]
    assert {item["thread_ts"] for item in client.messages} == {"1.1"}


def test_transport_returns_safe_error_when_handler_fails():
    client = RecordingSlackClient()
    def fail(_message):
        raise RuntimeError("private message body")
    SlackGateway(["U-allowed"], client, handler=fail).handle_envelope(dm_envelope())
    assert client.messages[0]["text"] == "I couldn't complete that request. Please try again."
