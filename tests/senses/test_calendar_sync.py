import sys
import types
from datetime import datetime, timezone

import pytest

from iris.senses import SenseStore, SourceItem
from iris.senses.calendar_sync import EventKitCalendarProvider, main, sync_calendar, _objc_value


class FakeProvider:
    def __init__(self, events):
        self.events = events

    def list_events(self):
        return list(self.events)


class FakeNSDate:
    @staticmethod
    def dateWithTimeIntervalSince1970_(value):
        return ("nsdate", value)


class FakeStartDate:
    def __init__(self, timestamp):
        self.timeIntervalSince1970 = timestamp


class FakeEvent:
    def __init__(self, event_id, title, timestamp, *, callable_fields=True):
        self._event_id = event_id
        self._title = title
        self._start = FakeStartDate(timestamp) if timestamp is not None else None
        if not callable_fields:
            self.eventIdentifier = event_id
            self.title = title
            self.startDate = self._start

    def eventIdentifier(self):
        return self._event_id

    def title(self):
        return self._title

    def startDate(self):
        return self._start


class FakeEventStore:
    def __init__(self, events=()):
        self.events = list(events)
        self.predicates = []

    def predicateForEventsWithStartDate_endDate_calendars_(self, start, end, calendars):
        self.predicates.append((start, end, calendars))
        return "predicate"

    def eventsMatchingPredicate_(self, predicate):
        assert predicate == "predicate"
        return self.events


def install_eventkit(monkeypatch, *, authorized=True, allocated_store=None):
    eventkit = types.ModuleType("EventKit")
    eventkit.EKAuthorizationStatusFullAccess = 3
    eventkit.EKEntityTypeEvent = 0

    class EKEventStore:
        @staticmethod
        def authorizationStatusForEntityType_(_entity):
            return 3 if authorized else 1

        @classmethod
        def alloc(cls):
            return cls()

        def init(self):
            return allocated_store or FakeEventStore()

    eventkit.EKEventStore = EKEventStore
    foundation = types.ModuleType("Foundation")
    foundation.NSDate = FakeNSDate
    monkeypatch.setitem(sys.modules, "EventKit", eventkit)
    monkeypatch.setitem(sys.modules, "Foundation", foundation)


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
    for days in (0, 366, "14", True):
        with pytest.raises(ValueError):
            EventKitCalendarProvider(days=days)


def test_objc_value_accepts_property_or_zero_argument_method():
    assert _objc_value(types.SimpleNamespace(value="property"), "value") == "property"
    assert _objc_value(types.SimpleNamespace(value=lambda: "method"), "value") == "method"
    assert _objc_value(object(), "missing") is None


def test_eventkit_provider_reads_bounded_window_and_filters_invalid_rows(monkeypatch):
    store = FakeEventStore([
        FakeEvent("good", "Design review", 1_800_000_000),
        FakeEvent("property", "Property fields", 1_800_000_100, callable_fields=False),
        FakeEvent("", "missing id", 1_800_000_200),
        FakeEvent("bad-title", None, 1_800_000_300),
        FakeEvent("bad-time", "No timestamp", None),
        FakeEvent("bad-time-type", "Wrong timestamp", "tomorrow"),
    ])
    install_eventkit(monkeypatch, allocated_store=store)
    now = datetime(2026, 8, 20, 12, tzinfo=timezone.utc)

    rows = EventKitCalendarProvider(days=2, now=lambda: now).list_events()

    assert [row["id"] for row in rows] == ["good", "property"]
    assert rows[0]["starts_at"] == datetime.fromtimestamp(1_800_000_000, tz=timezone.utc).isoformat()
    assert len(store.predicates) == 1
    start, end, calendars = store.predicates[0]
    assert start == ("nsdate", now.timestamp())
    assert end == ("nsdate", (now.replace() + __import__("datetime").timedelta(days=2)).timestamp())
    assert calendars is None


def test_eventkit_provider_denies_without_calendar_authorization(monkeypatch):
    install_eventkit(monkeypatch, authorized=False)
    with pytest.raises(PermissionError, match="Calendar access is not granted"):
        EventKitCalendarProvider().list_events()


def test_eventkit_provider_uses_allocated_store_when_not_injected(monkeypatch):
    allocated = FakeEventStore([FakeEvent("e1", "Allocated", 1_800_000_000)])
    install_eventkit(monkeypatch, allocated_store=allocated)
    assert EventKitCalendarProvider().list_events()[0]["id"] == "e1"


def test_eventkit_provider_treats_none_event_collection_as_empty(monkeypatch):
    class NoneStore(FakeEventStore):
        def eventsMatchingPredicate_(self, predicate):
            assert predicate == "predicate"
            return None

    install_eventkit(monkeypatch)
    assert EventKitCalendarProvider(store=NoneStore()).list_events() == []


def test_calendar_sync_cli_success_and_failure(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr("iris.senses.calendar_sync.sync_calendar", lambda path, days: 3)
    assert main(["--state-dir", str(tmp_path), "--days", "30"]) == 0
    assert "3 upcoming event(s)" in capsys.readouterr().out

    def fail(_path, *, days):
        raise PermissionError(f"denied for {days}")

    monkeypatch.setattr("iris.senses.calendar_sync.sync_calendar", fail)
    assert main(["--state-dir", str(tmp_path), "--days", "10"]) == 1
    assert "Calendar sync failed: denied for 10" in capsys.readouterr().out
