import sys
import types
from types import SimpleNamespace

import pytest

from iris.slack import SlackGateway, SlackMessage, SlackWebClient, SocketModeEventSource
from iris.slack_config import SlackCredentials


def envelope(*, event_id="E1", event=None, outer_type="events_api"):
    return {
        "type": outer_type,
        "event_id": event_id,
        "event": event if event is not None else {
            "type": "message",
            "user": "U1",
            "channel": "D1",
            "text": "hello",
            "ts": "1.0",
            "channel_type": "im",
        },
    }


def test_slack_message_decoder_rejects_every_malformed_envelope_class():
    assert SlackMessage.from_envelope(envelope(outer_type="hello")) is None
    assert SlackMessage.from_envelope({"type": "events_api", "event": []}) is None
    assert SlackMessage.from_envelope(envelope(event={"type": "reaction_added"})) is None
    for key in ("user", "channel", "text", "ts"):
        event = envelope()["event"].copy()
        event[key] = ""
        assert SlackMessage.from_envelope(envelope(event=event)) is None
    assert SlackMessage.from_envelope(envelope(event_id="")) is None
    assert SlackMessage.from_envelope(envelope(event_id=123)) is None


def test_slack_message_decoder_normalizes_optional_fields_and_reply_thread():
    event = envelope()["event"] | {
        "thread_ts": "0.5",
        "bot_id": "B1",
        "subtype": "bot_message",
        "channel_type": "im",
    }
    message = SlackMessage.from_envelope(envelope(event=event))
    assert message.reply_thread_ts == "0.5"
    assert (message.bot_id, message.subtype, message.channel_type) == ("B1", "bot_message", "im")

    event |= {"thread_ts": 7, "bot_id": 8, "subtype": 9, "channel_type": 10}
    message = SlackMessage.from_envelope(envelope(event=event, event_id="E2"))
    assert message.thread_ts is None
    assert message.reply_thread_ts == "1.0"
    assert message.bot_id is message.subtype is message.channel_type is None


class Client:
    def __init__(self):
        self.posts = []

    def post_message(self, **kwargs):
        self.posts.append(kwargs)


class Audit:
    def __init__(self):
        self.rows = []

    def append(self, kind, **payload):
        self.rows.append((kind, payload))


def test_gateway_filters_transport_noise_before_handler():
    called = []
    gateway = SlackGateway(("U1",), Client(), handler=lambda message: called.append(message) or "ok")
    assert gateway.handle_envelope({"type": "hello"}) is False

    for index, mutation in enumerate((
        {"channel_type": "channel"},
        {"bot_id": "B1"},
        {"subtype": "message_changed"},
    ), start=1):
        event = envelope()["event"] | mutation
        assert gateway.handle_envelope(envelope(event_id=f"E{index}", event=event)) is False
    assert called == []


def test_gateway_rejection_is_audited_without_reply():
    audit, client = Audit(), Client()
    gateway = SlackGateway(("U1",), client, audit=audit)
    assert gateway.handle_envelope(envelope(event_id="reject", event=envelope()["event"] | {"user": "U2"})) is False
    assert client.posts == []
    assert audit.rows[0][0] == "rejected_inbound"
    assert audit.rows[0][1]["event_id"] == "reject"
    assert "hello" not in repr(audit.rows[0][1])


def test_gateway_handler_error_fails_safe_and_records_activity():
    client, audit, activity = Client(), Audit(), []

    def fail(_message):
        raise RuntimeError("boom")

    gateway = SlackGateway(("U1",), client, handler=fail, audit=audit,
                           on_inbound=lambda: activity.append("in"),
                           on_outbound=lambda: activity.append("out"))
    assert gateway.handle_envelope(envelope()) is True
    assert client.posts == [{
        "channel_id": "D1",
        "text": "I couldn't complete that request. Please try again.",
        "thread_ts": "1.0",
    }]
    assert activity == ["in", "out"]
    assert audit.rows[0] == ("inbound", {
        "event_id": "E1", "user_id": "U1", "channel_id": "D1", "thread_ts": "1.0"
    })


def test_gateway_long_response_uses_splitter_and_thread_reply():
    client, activity = Client(), []
    splitter_calls = []

    def splitter(text):
        splitter_calls.append(text)
        return ("part one", "part two")

    gateway = SlackGateway(("U1",), client, handler=lambda _message: "x" * 3001,
                           splitter=splitter, on_outbound=lambda: activity.append("out"))
    event = envelope()["event"] | {"thread_ts": "0.5"}
    assert gateway.handle_envelope(envelope(event=event)) is True
    assert splitter_calls == ["x" * 3001]
    assert [post["text"] for post in client.posts] == ["part one", "part two"]
    assert all(post["thread_ts"] == "0.5" for post in client.posts)
    assert activity == ["out", "out"]


def test_gateway_without_handler_echoes_and_deduplicates():
    client = Client()
    gateway = SlackGateway(("U1",), client)
    event = envelope(event_id="same")
    assert gateway.handle_envelope(event) is True
    assert gateway.handle_envelope(event) is False
    assert client.posts[0]["text"] == "hello"


def test_gateway_run_forever_delegates_to_source():
    calls = []

    class Source:
        def run(self, handler, *, stop):
            calls.append((handler, stop))

    gateway = SlackGateway(("U1",), Client())
    stop = lambda: True
    gateway.run_forever(Source(), stop=stop)
    assert calls == [(gateway.handle_envelope, stop)]


def test_slack_web_client_wraps_sdk_without_leaking_interface(monkeypatch):
    posts = []

    class SDKClient:
        def __init__(self, *, token):
            assert token == "xoxb-secret"

        def chat_postMessage(self, **kwargs):
            posts.append(kwargs)

    module = types.ModuleType("slack_sdk")
    module.WebClient = SDKClient
    monkeypatch.setitem(sys.modules, "slack_sdk", module)
    client = SlackWebClient("xoxb-secret")
    client.post_message(channel_id="D1", text="reply", thread_ts="1.0")
    assert posts == [{"channel": "D1", "text": "reply", "thread_ts": "1.0"}]


def install_socket_sdk(monkeypatch, *, connect_error=None):
    created = []

    class Response:
        def __init__(self, *, envelope_id):
            self.envelope_id = envelope_id

    class Request:
        envelope_id = "ENV1"
        type = "events_api"
        payload = {"event_id": "E1", "event": {"type": "message"}}

    class SocketClient:
        def __init__(self, *, app_token):
            self.app_token = app_token
            self.message_listeners = []
            self.socket_mode_request_listeners = []
            self.responses = []
            self.closed = False
            created.append(self)

        def send_socket_mode_response(self, response):
            self.responses.append(response.envelope_id)

        def connect(self):
            if connect_error:
                raise connect_error
            for listener in self.message_listeners:
                listener(self, {"type": "hello"}, "raw")
                listener(self, "not-a-dict", "raw")
            for listener in self.socket_mode_request_listeners:
                listener(self, Request())

        def close(self):
            self.closed = True

    socket_module = types.ModuleType("slack_sdk.socket_mode")
    socket_module.SocketModeClient = SocketClient
    response_module = types.ModuleType("slack_sdk.socket_mode.response")
    response_module.SocketModeResponse = Response
    monkeypatch.setitem(sys.modules, "slack_sdk.socket_mode", socket_module)
    monkeypatch.setitem(sys.modules, "slack_sdk.socket_mode.response", response_module)
    return created


def test_socket_mode_source_acks_dispatches_and_reports_lifecycle(monkeypatch):
    created = install_socket_sdk(monkeypatch)
    events, lifecycle = [], []
    source = SocketModeEventSource(SlackCredentials("xapp-token", "xoxb-token"))
    source.run(events.append, stop=lambda: True,
               on_connected=lambda: lifecycle.append("connected"),
               on_disconnected=lambda error=None: lifecycle.append(("disconnected", error)))

    client = created[0]
    assert client.app_token == "xapp-token"
    assert client.responses == ["ENV1"]
    assert events == [{"event_id": "E1", "event": {"type": "message"}, "type": "events_api"}]
    assert lifecycle == ["connected", ("disconnected", None)]
    assert client.closed is True


def test_socket_mode_source_reports_connect_failure(monkeypatch):
    failure = ConnectionError("no socket")
    created = install_socket_sdk(monkeypatch, connect_error=failure)
    disconnected = []
    source = SocketModeEventSource(SlackCredentials("xapp-token", "xoxb-token"))

    with pytest.raises(ConnectionError, match="no socket"):
        source.run(lambda _event: None, stop=lambda: True,
                   on_disconnected=disconnected.append)

    assert disconnected == [failure]
    assert created[0].closed is False
