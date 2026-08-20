import pytest

from iris.memory import MemoryPolicyError, MemoryStore


def test_blank_claim_or_provenance_and_out_of_range_confidence_are_refused(tmp_path):
    store = MemoryStore(tmp_path / "memory.json")
    rejected = (
        {"claim": "   ", "source_ref": "slack:1"},
        {"claim": "a real claim", "source_ref": "   "},
        {"claim": "a real claim", "source_ref": "slack:1", "confidence": -0.1},
        {"claim": "a real claim", "source_ref": "slack:1", "confidence": 1.1},
    )
    for arguments in rejected:
        with pytest.raises(MemoryPolicyError):
            store.remember(**arguments)
    assert store.retrieve() == ()
    assert not (tmp_path / "memory.json").exists()
