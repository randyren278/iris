"""Read-only EventKit Calendar access probe with optional quarantined sync."""
from __future__ import annotations

import argparse
import pathlib
import threading

from EventKit import EKAuthorizationStatusFullAccess, EKEntityTypeEvent, EKEventStore

from iris.senses.calendar_sync import DEFAULT_DAYS, sync_calendar


def _ensure_access(store) -> bool:
    status = EKEventStore.authorizationStatusForEntityType_(EKEntityTypeEvent)
    if status == EKAuthorizationStatusFullAccess:
        return True
    done = threading.Event()
    result = []

    def completed(granted, _error):
        result.append(bool(granted))
        done.set()
        return None

    store.requestFullAccessToEventsWithCompletion_(completed)
    done.wait(30)
    return bool(result and result[0])


def main(argv=None):
    parser = argparse.ArgumentParser(prog="iris-calendar-probe")
    parser.add_argument("--sync", action="store_true",
                        help="also refresh ~/.iris/senses.json with upcoming events")
    parser.add_argument("--state-dir", default=str(pathlib.Path.home() / ".iris"))
    parser.add_argument("--days", type=int, default=DEFAULT_DAYS)
    args = parser.parse_args(argv)

    store = EKEventStore.alloc().init()
    if not _ensure_access(store):
        print("Calendar access was not granted.")
        return 1
    calendars = store.calendarsForEntityType_(EKEntityTypeEvent)
    print(f"Calendar read-only access verified ({len(calendars)} calendars).")
    if args.sync:
        try:
            count = sync_calendar(pathlib.Path(args.state_dir) / "senses.json", days=args.days)
        except (PermissionError, RuntimeError, ValueError) as error:
            print(f"Calendar sync failed: {error}")
            return 1
        print(f"Calendar sync complete: {count} upcoming event(s) quarantined as untrusted data.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
