#!/usr/bin/env python3
"""CP-1.2 spike: confirm a sent message actually landed in chat.db.

    python3 spikes/assert_sent.py 'iris CP-1.2 probe' --within-seconds 60

Exits 0 if a row exists with is_from_me=1, matching text, dated within the
window. Prints the observed send latency, which is the number CP-1.2 records.
"""
import argparse
import datetime as dt
import pathlib
import sqlite3
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from iris.chatdb import message_body  # noqa: E402

CHATDB = pathlib.Path.home() / "Library/Messages/chat.db"
APPLE_EPOCH = dt.datetime(2001, 1, 1, tzinfo=dt.timezone.utc)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("text", help="exact message body to look for")
    ap.add_argument("--within-seconds", type=int, default=60,
                    help="how far back to look (default 60)")
    args = ap.parse_args()

    now = dt.datetime.now(dt.timezone.utc)
    cutoff_ns = int((now - dt.timedelta(seconds=args.within_seconds)
                     - APPLE_EPOCH).total_seconds() * 1e9)

    # `text` cannot be matched in SQL: it is NULL for ~99% of rows, with the
    # body held in the attributedBody typedstream instead (see chatdb_text).
    # Scan the candidate window and compare decoded bodies for exact equality.
    try:
        conn = sqlite3.connect(f"file:{CHATDB}?mode=ro", uri=True)
        candidates = conn.execute(
            "select ROWID, handle_id, text, attributedBody, date from message "
            "where is_from_me = 1 and date >= ? "
            "order by ROWID desc",
            (cutoff_ns,)).fetchall()
    except sqlite3.OperationalError as e:
        sys.stderr.write(
            f"cannot read {CHATDB}: {e}\n"
            f"Grant Full Disk Access to {sys.executable}.\n")
        return 1

    rows = [(rid, hid, body, date)
            for rid, hid, text, abody, date in candidates
            if (body := message_body(text, abody)) == args.text]

    if not rows:
        sys.stderr.write(
            f"no outbound message matching {args.text!r} in the last "
            f"{args.within_seconds}s "
            f"({len(candidates)} outbound row(s) in window)\n")
        return 1

    rowid, handle_id, text, date = rows[0]
    sent = APPLE_EPOCH + dt.timedelta(seconds=date / 1e9)
    print(f"found ROWID={rowid} handle_id={handle_id} text={text!r}")
    print(f"sent at {sent.astimezone().isoformat()}")
    print(f"observed age: {(now - sent).total_seconds():.1f}s "
          f"(window {args.within_seconds}s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
