#!/usr/bin/env python3
"""Assert the fake chat.db's schema is a faithful subset of the real one.

The real `message` table has 95 columns; reproducing all of them would be
noise. The contract that actually matters is one-directional:

    every column the fake declares must exist in the real chat.db,
    with the same declared type.

That catches the failure this harness exists to prevent -- the fake drifting
into a shape production does not have, so tests pass against a database that
does not exist. It deliberately does not require the reverse, since Iris reads
only a handful of the 95.

Skips (exit 0) if the real chat.db is unreadable, so the suite still runs on a
machine without Full Disk Access; CP-1.1 is what proves it is readable here.
"""
import pathlib
import sqlite3
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from tests.fakedb import (  # noqa: E402
    CHAT_COLUMNS,
    CHAT_HANDLE_JOIN_COLUMNS,
    CHAT_MESSAGE_JOIN_COLUMNS,
    HANDLE_COLUMNS,
    MESSAGE_COLUMNS,
)

REAL = pathlib.Path.home() / "Library/Messages/chat.db"


def real_columns(conn, table):
    return {r[1]: r[2] for r in conn.execute(f"pragma table_info({table})")}


def main():
    try:
        conn = sqlite3.connect(f"file:{REAL}?mode=ro", uri=True)
        conn.execute("select 1 from message limit 1")
    except sqlite3.OperationalError as e:
        print(f"SKIP: real chat.db unreadable ({e})")
        return 0

    problems = []
    for table, declared in (("message", MESSAGE_COLUMNS),
                            ("handle", HANDLE_COLUMNS),
                            ("chat", CHAT_COLUMNS),
                            ("chat_message_join", CHAT_MESSAGE_JOIN_COLUMNS),
                            ("chat_handle_join", CHAT_HANDLE_JOIN_COLUMNS)):
        actual = real_columns(conn, table)
        for name, typ in declared:
            if name not in actual:
                problems.append(f"{table}.{name} missing from real chat.db")
            elif actual[name] != typ:
                problems.append(
                    f"{table}.{name} type {typ!r} != real {actual[name]!r}")
        print(f"{table}: {len(declared)} fake columns checked "
              f"against {len(actual)} real")

    if problems:
        for p in problems:
            sys.stderr.write(f"schema parity: {p}\n")
        return 1
    print("schema parity OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
