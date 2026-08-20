import os

import pytest

from iris.memory import MemoryStore


def test_failed_replace_leaves_no_partial_memory_file_behind(tmp_path, monkeypatch):
    store = MemoryStore(tmp_path / "memory.json", ids=lambda: "m1")

    def failing_replace(_source, _destination):
        raise OSError("disk full")

    monkeypatch.setattr(os, "replace", failing_replace)
    with pytest.raises(OSError):
        store.remember("Prefer concise replies", source_ref="slack:1")

    assert not (tmp_path / "memory.json").exists()
    assert list(tmp_path.glob(".memory-*")) == []
