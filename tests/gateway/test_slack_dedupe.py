from iris.slack import SlackGateway
from tests.gateway.test_slack_echo_e2e import dm_envelope
from tests.slack_fakes import RecordingSlackClient


def test_ignores_bot_events_and_retries():
    client = RecordingSlackClient()
    gateway = SlackGateway(["U-allowed"], client)
    retry = dm_envelope(event_id="Ev-retry")
    bot = dm_envelope(event_id="Ev-bot")
    bot["event"]["bot_id"] = "B-iris"

    assert gateway.handle_envelope(retry) is True
    assert gateway.handle_envelope(retry) is False
    assert gateway.handle_envelope(bot) is False
    assert len(client.messages) == 1
