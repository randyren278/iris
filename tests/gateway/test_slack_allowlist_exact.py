"""Slack allowlist matching is exact -- no prefix, substring, or normalisation.

Slack user IDs share a common prefix by construction, so a loose comparison is
not a hypothetical: any workspace member whose ID contains, or is contained
by, the operator's would inherit the operator's authority over Iris.
"""
import pytest

from iris.slack import SlackGateway
from tests.slack_fakes import RecordingSlackClient

OPERATOR = "U0ABCDEF"


def _dm_from(user_id):
    return {"type": "events_api", "event_id": f"Ev-{user_id}", "event": {
        "type": "message", "user": user_id, "channel": "D-1", "channel_type": "im",
        "text": "start a session", "ts": "1.1",
    }}


@pytest.mark.parametrize("impostor", [
    "U0ABCDE",     # a prefix of the operator's id
    "U0ABCDEFG",   # the operator's id with a suffix
    "0ABCDEF",     # the operator's id with its leading character stripped
    "u0abcdef",    # same id, different case
    " U0ABCDEF",   # leading whitespace
    "U0ABCDEF ",   # trailing whitespace
])
def test_ids_that_merely_resemble_the_operator_are_refused(impostor):
    client = RecordingSlackClient()
    reached = []
    gateway = SlackGateway([OPERATOR], client,
                           handler=lambda message: reached.append(message) or "handled")

    assert gateway.handle_envelope(_dm_from(impostor)) is False
    assert reached == []
    assert client.messages == []


def test_the_exact_operator_id_is_still_accepted():
    client = RecordingSlackClient()
    reached = []
    gateway = SlackGateway([OPERATOR], client,
                           handler=lambda message: reached.append(message) or "handled")

    assert gateway.handle_envelope(_dm_from(OPERATOR)) is True
    assert [message.user_id for message in reached] == [OPERATOR]
