import pytest

from iris.hera_memory import HeraMemoryAdapter
from iris.memory import MemoryRecord


def test_hera_adapter_refuses_untrusted_or_unconfirmed_records(tmp_path):
    record = MemoryRecord("m", "bad", "email:1", "untrusted", "operator_confirmed", 1, 1, 1)
    with pytest.raises(ValueError):
        HeraMemoryAdapter(tmp_path).ingest(record)
