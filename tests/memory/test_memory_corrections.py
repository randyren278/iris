from iris.memory import MemoryStore


def test_correction_supersedes_without_erasing_history(tmp_path):
    store = MemoryStore(tmp_path / "memory.json", ids=iter(["old", "new"]).__next__)
    old = store.remember("Lives in Manila", source_ref="slack:1")
    new = store.correct(old.id, "Lives in Cebu", source_ref="slack:2")
    assert store.retrieve() == (new,)
    assert new.supersedes == old.id
