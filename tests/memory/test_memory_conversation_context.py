from types import SimpleNamespace

from iris.conversation import ConversationCoordinator
from iris.memory import MemoryStore


class Backend:
    def __init__(self): self.context = ()
    def reply(self, _turns, context): self.context = context; return "ok"


def test_confirmed_memory_is_labeled_context_for_matching_conversation(tmp_path):
    store = MemoryStore(tmp_path / "memory.json")
    store.remember("Prefers concise answers", source_ref="slack:D1:1")
    backend = Backend()
    coordinator = ConversationCoordinator(
        backend, context_provider=lambda _key, query: tuple(
            type("Context", (), {"text": item.claim, "trust": item.trust, "provenance": item.source_ref})()
            for item in store.retrieve(query)))
    coordinator.reply(SimpleNamespace(channel_id="D1", reply_thread_ts="1", text="concise answer please"))
    assert backend.context[0].provenance == "slack:D1:1"
