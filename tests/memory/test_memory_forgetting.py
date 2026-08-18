from iris.memory import MemoryStore


def test_forgetting_hides_record_but_retains_tombstone(tmp_path):
    store = MemoryStore(tmp_path / "memory.json", ids=lambda: "m1")
    record = store.remember("Old preference", source_ref="slack:1")
    assert store.forget(record.id).lifecycle == "forgotten"
    assert store.retrieve() == ()
    assert '"lifecycle": "forgotten"' in (tmp_path / "memory.json").read_text()
