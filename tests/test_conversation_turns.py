from types import SimpleNamespace

from iris.conversation import ConversationCoordinator


class Backend:
    def __init__(self):
        self.calls = []

    def reply(self, messages, context):
        self.calls.append((messages, context))
        return "I can help with that."


def message(text, ts="1.1"):
    return SimpleNamespace(channel_id="D-1", reply_thread_ts=ts, text=text)


def test_normal_text_receives_an_agentic_reply_in_its_own_thread():
    backend = Backend()
    coordinator = ConversationCoordinator(backend)

    assert coordinator.reply(message("what should we work on?")) == "I can help with that."
    assert backend.calls[0][0][-1].text == "what should we work on?"


def test_threads_do_not_share_conversational_history():
    backend = Backend()
    coordinator = ConversationCoordinator(backend)
    coordinator.reply(message("first", "1.1"))
    coordinator.reply(message("second", "2.2"))

    assert [turn.text for turn in backend.calls[1][0]] == ["second"]
