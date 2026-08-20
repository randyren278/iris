import pytest

from iris.senses import SenseStore, SourceItem
from iris.senses.calendar_sync import EventKitCalendarProvider, sync_calendar


class FakeProvider:
    def __init__(self, events):
        self.events = events

    def list_events(self):
        return list(self.events)


def test_operator_calendar_sync_populates_quarantine(tmp_path):
    path = tmp_path / "senses.json"
    count = sync_calendar(path, provider=FakeProvider([
        {"id": "e1", "starts_at": "2026-08-21T01:00:00+00:00", "title": "Design review"},
        {"id": "e2", "starts_at": "2026-08-22T05:30:00+00:00", "title": "Supplier call"},
    ]))

    assert count == 2
    items = SenseStore(path).items()
    assert [item.item_id for item in items] == ["e1", "e2"]
    assert all(item.source_id == "calendar" and item.trust == "untrusted" for item in items)


def test_calendar_sync_replaces_only_calendar_source(tmp_path):
    path = tmp_path / "senses.json"
    store = SenseStore(path)
    store.ingest_calendar((SourceItem("other", "keep", "2026-08-20T00:00:00Z", "Keep me"),))
    sync_calendar(path, provider=FakeProvider([
        {"id": "fresh", "starts_at": "2026-08-23T00:00:00+00:00", "title": "Fresh event"},
    ]))

    items = SenseStore(path).items()
    assert {(item.source_id, item.item_id) for item in items} == {("other", "keep"), ("calendar", "fresh")}


def test_calendar_provider_bounds_sync_horizon():
    with pytest.raises(ValueError):
        EventKitCalendarProvider(days=0)
    with pytest.raises(ValueError):
        EventKitCalendarProvider(days=366)
