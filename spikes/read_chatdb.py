#!/usr/bin/env python3
"""CP-1.1 spike: prove ~/Library/Messages/chat.db is readable, read-only.

Opens the database through a `file:...?mode=ro` URI so SQLite itself refuses
any write, counts rows in `message`, and prints the 3 most recent rows.

    python3 spikes/read_chatdb.py
    python3 spikes/read_chatdb.py --count-only

Requires Full Disk Access on the *interpreter binary*, not just the terminal.
"""
import argparse
import datetime as dt
import pathlib
import sqlite3
import sys

CHATDB = pathlib.Path.home() / "Library/Messages/chat.db"
# Apple stores `message.date` as nanoseconds since 2001-01-01 UTC.
APPLE_EPOCH = dt.datetime(2001, 1, 1, tzinfo=dt.timezone.utc)


def connect():
    return sqlite3.connect(f"file:{CHATDB}?mode=ro", uri=True)


def apple_date(raw):
    if raw is None:
        return "?"
    return (APPLE_EPOCH + dt.timedelta(seconds=raw / 1e9)).astimezone().isoformat()


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--count-only", action="store_true",
                    help="print only the message row count")
    args = ap.parse_args()

    if not CHATDB.exists():
        sys.stderr.write(f"chat.db not found at {CHATDB}\n")
        return 1
    try:
        conn = connect()
        count = conn.execute("select count(*) from message").fetchone()[0]
    except sqlite3.OperationalError as e:
        sys.stderr.write(
            f"cannot read {CHATDB}: {e}\n"
            f"Grant Full Disk Access to {sys.executable} "
            f"(System Settings -> Privacy & Security -> Full Disk Access).\n")
        return 1

    if args.count_only:
        print(count)
        return 0

    print(f"chat.db: {CHATDB}")
    print(f"opened read-only via file:...?mode=ro")
    print(f"message rows: {count}")
    print("3 most recent messages (ROWID, is_from_me, handle_id, text, date):")
    rows = conn.execute(
        "select ROWID, is_from_me, handle_id, text, date "
        "from message order by ROWID desc limit 3").fetchall()
    for rowid, from_me, handle_id, text, date in rows:
        body = text if text is not None else "<NULL: attributedBody only>"
        if len(body) > 120:
            body = body[:117] + "..."
        print(f"  {rowid} is_from_me={from_me} handle_id={handle_id} "
              f"date={date} ({apple_date(date)}) text={body!r}")
    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
