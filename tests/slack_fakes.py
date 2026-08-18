"""Test doubles for the Slack transport boundary."""


class FakeEventSource:
    def __init__(self, envelopes=()):
        self.envelopes = list(envelopes)

    def run(self, handler, *, stop=None):
        for envelope in self.envelopes:
            handler(envelope)


class RecordingSlackClient:
    def __init__(self):
        self.messages = []

    def post_message(self, *, channel_id, text, thread_ts):
        self.messages.append({
            "channel_id": channel_id,
            "text": text,
            "thread_ts": thread_ts,
        })
