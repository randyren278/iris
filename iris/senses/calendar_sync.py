"""Operator-run, read-only EventKit Calendar ingestion into Iris quarantine."""
from __future__ import annotations

import argparse
import pathlib
from datetime import datetime, timedelta, timezone

from iris.senses import CalendarSense, SenseStore

DEFAULT_DAYS = 14
MAX_DAYS = 365


def _objc_value(value, name):
    attribute = getattr(value, name, None)
    return attribute() if callable(attribute) else attribute


class EventKitCalendarProvider:
    """Read upcoming events from EventKit without exposing any write surface."""

    def __init__(self, *, days: int = DEFAULT_DAYS, now=None, store=None):
        # bool is an int subclass in Python; accepting True here would silently
        # turn an invalid configuration into a one-day Calendar window.
        if isinstance(days, bool) or not isinstance(days, int) or not 1 <= days <= MAX_DAYS:
            raise ValueError(f"days must be between 1 and {MAX_DAYS}")
        self.days = days
        self._now = now or (lambda: datetime.now(timezone.utc))
        self._store = store

    def list_events(self) -> list[dict[str, str]]:
        try:
            from EventKit import (
                EKAuthorizationStatusFullAccess,
                EKEntityTypeEvent,
                EKEventStore,
            )
            from Foundation import NSDate
        except ImportError as error:  # pragma: no cover - macOS dependency
            raise RuntimeError("Calendar sync requires macOS EventKit support") from error

        if EKEventStore.authorizationStatusForEntityType_(EKEntityTypeEvent) != EKAuthorizationStatusFullAccess:
            raise PermissionError(
                "Calendar access is not granted. Run `python -m iris.senses.calendar_probe` first."
            )
        store = self._store or EKEventStore.alloc().init()
        start = self._now().astimezone(timezone.utc)
        end = start + timedelta(days=self.days)
        start_date = NSDate.dateWithTimeIntervalSince1970_(start.timestamp())
        end_date = NSDate.dateWithTimeIntervalSince1970_(end.timestamp())
        predicate = store.predicateForEventsWithStartDate_endDate_calendars_(start_date, end_date, None)
        events = store.eventsMatchingPredicate_(predicate) or ()

        rows: list[dict[str, str]] = []
        for event in events:
            event_id = _objc_value(event, "eventIdentifier")
            title = _objc_value(event, "title")
            start_value = _objc_value(event, "startDate")
            timestamp = _objc_value(start_value, "timeIntervalSince1970") if start_value is not None else None
            if not isinstance(event_id, str) or not event_id or not isinstance(title, str):
                continue
            if not isinstance(timestamp, (int, float)):
                continue
            starts_at = datetime.fromtimestamp(timestamp, tz=timezone.utc).isoformat()
            rows.append({"id": event_id, "starts_at": starts_at, "title": title})
        return rows


def sync_calendar(path: pathlib.Path | str, *, provider=None, days: int = DEFAULT_DAYS) -> int:
    """Replace the quarantined Calendar source with a fresh read-only snapshot."""
    store = SenseStore(path)
    CalendarSense(provider or EventKitCalendarProvider(days=days), store).sync()
    return sum(1 for item in store.items() if item.source_id == "calendar")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="iris-calendar-sync")
    parser.add_argument("--state-dir", default=str(pathlib.Path.home() / ".iris"))
    parser.add_argument("--days", type=int, default=DEFAULT_DAYS)
    args = parser.parse_args(argv)
    try:
        count = sync_calendar(pathlib.Path(args.state_dir) / "senses.json", days=args.days)
    except (PermissionError, RuntimeError, ValueError) as error:
        print(f"Calendar sync failed: {error}")
        return 1
    print(f"Calendar sync complete: {count} upcoming event(s) quarantined as untrusted data.")
    return 0


if __name__ == "__main__":  # pragma: no cover - operator CLI
    raise SystemExit(main())
