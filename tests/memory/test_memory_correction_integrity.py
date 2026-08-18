import pytest

from iris.memory import MemoryPolicyError, MemoryStore


def test_correcting_the_same_record_twice_leaves_only_the_latest_live(tmp_path):
    store = MemoryStore(tmp_path / "memory.json", ids=iter(["old", "new1", "new2"]).__next__)
    old = store.remember("Lives in Manila", source_ref="slack:1")
    store.correct(old.id, "Lives in Cebu", source_ref="slack:2")
    with pytest.raises(MemoryPolicyError):
        store.correct(old.id, "Lives in Davao", source_ref="slack:3")
    assert [item.claim for item in store.retrieve()] == ["Lives in Cebu"]


def test_correcting_a_forgotten_record_does_not_revive_it(tmp_path):
    store = MemoryStore(tmp_path / "memory.json", ids=iter(["a", "b"]).__next__)
    record = store.remember("Old preference", source_ref="slack:1")
    store.forget(record.id)
    with pytest.raises(MemoryPolicyError):
        store.correct(record.id, "revived claim", source_ref="slack:9")
    assert store.retrieve() == ()
