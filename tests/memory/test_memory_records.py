from iris.memory import MemoryStore


def test_confirmed_memory_round_trips_with_provenance(tmp_path):
    store = MemoryStore(tmp_path / "memory.json", clock=lambda: 12, ids=lambda: "m1")
    record = store.remember("Prefer concise replies", source_ref="slack:D1:1.2")
    assert store.retrieve("concise") == (record,)
    assert record.source_ref == "slack:D1:1.2"
