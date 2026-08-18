from types import SimpleNamespace

from iris.conversation import ConversationCoordinator, MemoryContext


class Backend:
    def reply(self, _messages, context):
        return ", ".join(item.text for item in context)


def test_context_is_bounded_and_kept_per_dm_thread():
    seen = []
    coordinator = ConversationCoordinator(
        Backend(), max_messages=2,
        context_provider=lambda key: seen.append(key) or (MemoryContext("prefers concise", "self", "operator"),),
    )
    message = SimpleNamespace(channel_id="D", reply_thread_ts="T", text="one")
    assert coordinator.reply(message) == "prefers concise"
    message.text = "two"
    coordinator.reply(message)
    assert seen == [("D", "T"), ("D", "T")]
