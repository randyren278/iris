from types import SimpleNamespace

from iris.conversation import ConversationCoordinator
from iris.grammar import parse


class Backend:
    def reply(self, messages, _context):
        return f"I only discussed: {messages[-1].text}"


def test_natural_language_that_mentions_an_action_is_not_a_control_command():
    text = "please stop every coding session now"
    assert parse(text) is None
    coordinator = ConversationCoordinator(Backend())
    message = SimpleNamespace(channel_id="D", reply_thread_ts="T", text=text)
    assert "discussed" in coordinator.reply(message)
