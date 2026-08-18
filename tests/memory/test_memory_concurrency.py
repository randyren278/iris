import threading

from iris.memory import MemoryStore


def test_concurrent_remembers_do_not_lose_updates(tmp_path):
    store = MemoryStore(tmp_path / "memory.json")
    real_load = store._load
    entered_first_load = threading.Event()
    release_first_load = threading.Event()
    calls = {"n": 0}

    def hooked_load():
        calls["n"] += 1
        if calls["n"] == 1:
            result = real_load()
            entered_first_load.set()
            release_first_load.wait(2)
            return result
        return real_load()

    store._load = hooked_load

    thread_a = threading.Thread(target=lambda: store.remember("claim A", source_ref="slack:1"))
    thread_a.start()
    assert entered_first_load.wait(2)

    thread_b = threading.Thread(target=lambda: store.remember("claim B", source_ref="slack:2"))
    thread_b.start()
    release_first_load.set()
    thread_a.join(2)
    thread_b.join(2)

    assert {item.claim for item in store.retrieve()} == {"claim A", "claim B"}
