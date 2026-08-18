from iris.slack import SlackGateway
from tests.test_slack_echo_e2e import dm_envelope
from tests.slack_fakes import RecordingSlackClient


def test_unknown_user_is_silent():
    client = RecordingSlackClient()

    handled = SlackGateway(["U-allowed"], client).handle_envelope(
        dm_envelope(user_id="U-stranger", text="do not echo")
    )

    assert handled is False
    assert client.messages == []
