import pytest

from iris.memory import MemoryPolicyError, MemoryStore


def test_forgetting_an_unknown_record_is_refused(tmp_path):
    store = MemoryStore(tmp_path / "memory.json", ids=lambda: "m1")
    store.remember("Old preference", source_ref="slack:1")
    with pytest.raises(MemoryPolicyError):
        store.forget("m-does-not-exist")


def test_forgetting_hides_record_but_retains_tombstone(tmp_path):
    store = MemoryStore(tmp_path / "memory.json", ids=lambda: "m1")
    record = store.remember("Old preference", source_ref="slack:1")
    assert store.forget(record.id).lifecycle == "forgotten"
    assert store.retrieve() == ()
    assert '"lifecycle": "forgotten"' in (tmp_path / "memory.json").read_text()
