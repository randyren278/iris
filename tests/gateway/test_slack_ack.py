"""A slow turn is acknowledged at once, and that placeholder becomes the answer."""
from iris.slack import SlackGateway
from tests.gateway.test_slack_echo_e2e import dm_envelope
from tests.slack_fakes import RecordingSlackClient


def test_acknowledgement_is_posted_in_the_origin_thread_before_the_handler_runs():
    client = RecordingSlackClient()
    order = []

    def handler(_message):
        order.append(("handler", len(client.messages)))
        return "the answer"

    gateway = SlackGateway(["U-allowed"], client, handler=handler,
                           ack=lambda _message: "thinking…")

    gateway.handle_envelope(dm_envelope(ts="10.2", thread_ts="10.1"))

    # The acknowledgement was already posted when the handler was entered.
    assert order == [("handler", 1)]
    assert client.messages == [{"channel_id": "D-1", "text": "thinking…", "thread_ts": "10.1"}]


def test_first_reply_chunk_edits_the_acknowledgement_instead_of_posting_again():
    client = RecordingSlackClient()
    gateway = SlackGateway(["U-allowed"], client, handler=lambda _message: "the answer",
                           ack=lambda _message: "thinking…")

    gateway.handle_envelope(dm_envelope())

    assert [message["text"] for message in client.messages] == ["thinking…"]
    assert client.updates == [{"channel_id": "D-1", "ts": "posted-1", "text": "the answer"}]


def test_remaining_chunks_of_a_split_reply_post_below_the_edited_acknowledgement():
    client = RecordingSlackClient()
    activity = []
    gateway = SlackGateway(["U-allowed"], client, handler=lambda _message: "x" * 3001,
                           splitter=lambda _text: ("part one", "part two"),
                           ack=lambda _message: "thinking…",
                           on_outbound=lambda: activity.append("out"))

    gateway.handle_envelope(dm_envelope())

    assert [message["text"] for message in client.messages] == ["thinking…", "part two"]
    assert [update["text"] for update in client.updates] == ["part one"]
    # The acknowledgement counts as outbound activity, like every other post.
    assert activity == ["out", "out", "out"]


def test_no_acknowledgement_is_posted_when_the_callable_declines():
    client = RecordingSlackClient()
    gateway = SlackGateway(["U-allowed"], client, handler=lambda _message: "the answer",
                           ack=lambda _message: None)

    gateway.handle_envelope(dm_envelope())

    assert client.messages == [{"channel_id": "D-1", "text": "the answer", "thread_ts": "1.1"}]
    assert client.updates == []


def test_a_failing_acknowledgement_still_delivers_the_whole_reply():
    class FailingAckClient(RecordingSlackClient):
        def post_message(self, *, channel_id, text, thread_ts):
            if text == "thinking…":
                raise RuntimeError("slack refused the placeholder")
            return super().post_message(channel_id=channel_id, text=text, thread_ts=thread_ts)

    client = FailingAckClient()
    gateway = SlackGateway(["U-allowed"], client, handler=lambda _message: "the answer",
                           ack=lambda _message: "thinking…")

    assert gateway.handle_envelope(dm_envelope()) is True
    assert [message["text"] for message in client.messages] == ["the answer"]
    assert client.updates == []


def test_a_failing_edit_falls_back_to_posting_the_reply():
    class FailingUpdateClient(RecordingSlackClient):
        def update_message(self, *, channel_id, ts, text):
            raise RuntimeError("message is too old to edit")

    client = FailingUpdateClient()
    gateway = SlackGateway(["U-allowed"], client, handler=lambda _message: "the answer",
                           ack=lambda _message: "thinking…")

    gateway.handle_envelope(dm_envelope())

    assert [message["text"] for message in client.messages] == ["thinking…", "the answer"]


def test_a_client_without_a_usable_timestamp_posts_the_reply_rather_than_editing():
    class TimestamplessClient(RecordingSlackClient):
        def post_message(self, *, channel_id, text, thread_ts):
            super().post_message(channel_id=channel_id, text=text, thread_ts=thread_ts)
            return None

    client = TimestamplessClient()
    gateway = SlackGateway(["U-allowed"], client, handler=lambda _message: "the answer",
                           ack=lambda _message: "thinking…")

    gateway.handle_envelope(dm_envelope())

    assert [message["text"] for message in client.messages] == ["thinking…", "the answer"]
    assert client.updates == []


def test_gateway_without_an_ack_callable_is_unchanged():
    client = RecordingSlackClient()

    SlackGateway(["U-allowed"], client, handler=lambda _message: "the answer").handle_envelope(
        dm_envelope())

    assert [message["text"] for message in client.messages] == ["the answer"]
    assert client.updates == []


def test_rejected_sender_is_never_acknowledged():
    client = RecordingSlackClient()
    gateway = SlackGateway(["U-allowed"], client, handler=lambda _message: "the answer",
                           ack=lambda _message: "thinking…")

    assert gateway.handle_envelope(dm_envelope(user_id="U-stranger")) is False
    assert client.messages == []
