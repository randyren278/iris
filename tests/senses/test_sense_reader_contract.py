import pytest

from iris.senses import SenseStore, SourceItem
from iris.tools.senses import QuarantinedSenseReader, validate_sense_arguments


def test_sense_schema_accepts_only_empty_arguments():
    assert validate_sense_arguments({}) == {}
    for arguments in ({"source": "calendar"}, {"limit": 1}):
        with pytest.raises(ValueError, match="takes no arguments"):
            validate_sense_arguments(arguments)


def test_reader_returns_only_quarantined_structured_fields(tmp_path):
    store = SenseStore(tmp_path / "senses.json")
    store.ingest_calendar((
        SourceItem("calendar", "e2", "2026-08-22T10:00:00Z", "Later"),
        SourceItem("calendar", "e1", "2026-08-21T09:00:00Z", "Earlier"),
    ))
    rows = QuarantinedSenseReader(store)({})
    # The quarantine reader preserves the provider/store order; it does not
    # silently reorder source data while projecting the safe field set.
    assert rows == [
        {"source_id": "calendar", "item_id": "e2", "starts_at": "2026-08-22T10:00:00Z",
         "title": "Later", "trust": "untrusted"},
        {"source_id": "calendar", "item_id": "e1", "starts_at": "2026-08-21T09:00:00Z",
         "title": "Earlier", "trust": "untrusted"},
    ]
    assert all(set(row) == {"source_id", "item_id", "starts_at", "title", "trust"} for row in rows)


def test_reader_empty_store_returns_empty_list(tmp_path):
    assert QuarantinedSenseReader(SenseStore(tmp_path / "senses.json"))({}) == []
