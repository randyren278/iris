"""A fake chat.db that lies the way the real one lies.

The point of this harness is to make every later phase testable without a
phone. That is only true if the fake reproduces the real database's awkward
parts, not just its column names. The awkward part is A9: `message.text` is
NULL for ~99% of real rows and the body lives in `attributedBody` as a
typedstream. A fake that helpfully populates `text` would make the whole test
suite pass against a database far easier than production.

So `inject()` writes `text = NULL` and a real typedstream blob by default.
Passing `plain_text=True` produces the ~1% shape instead, so both paths stay
covered.
"""
import pathlib
import sqlite3
import time

APPLE_EPOCH_OFFSET = 978307200  # unix seconds at 2001-01-01Z

# Column subset Iris actually reads. assert_schema_parity.py checks every one
# of these exists in the real chat.db with the same declared type -- the fake
# is a subset of the real schema, never a divergent one.
MESSAGE_COLUMNS = [
    ("ROWID", "INTEGER"),
    ("guid", "TEXT"),
    ("text", "TEXT"),
    ("handle_id", "INTEGER"),
    ("attributedBody", "BLOB"),
    ("service", "TEXT"),
    ("date", "INTEGER"),
    ("is_from_me", "INTEGER"),
    ("is_read", "INTEGER"),
    ("cache_has_attachments", "INTEGER"),
]
HANDLE_COLUMNS = [
    ("ROWID", "INTEGER"),
    ("id", "TEXT"),
    ("country", "TEXT"),
    ("service", "TEXT"),
    ("uncanonicalized_id", "TEXT"),
]


def _typedstream(body):
    """Encode `body` the way Messages archives an NSAttributedString.

    Byte-for-byte compatible with the real layout through the string payload,
    which is the region iris.chatdb decodes. Verified by round-tripping this
    output back through the production decoder in tests/test_fakedb_a9.py.
    """
    raw = body.encode("utf-8")
    n = len(raw)
    if n < 0x80:
        length = bytes([n])
    else:
        length = b"\x81" + n.to_bytes(2, "little")
    return (
        b"\x04\x0bstreamtyped\x81\xe8\x03\x84\x01@\x84\x84"
        b"\x84\x12NSAttributedString\x00\x84\x84\x08NSObject\x00\x85\x92"
        b"\x84\x84\x84\x08NSString\x01\x94\x84\x01+"
        + length + raw
        + b"\x86\x84\x02iI\x01" + bytes([min(n, 0x7F)])
        + b"\x92\x84\x84\x84\x0cNSDictionary\x00\x94\x84\x01i\x01"
        b"\x92\x84\x96\x96\x1d__kIMMessagePartAttributeName\x86\x86"
    )


def _ddl(table, columns):
    body = ", ".join(
        f"{name} {typ}" + (" PRIMARY KEY AUTOINCREMENT" if name == "ROWID" else "")
        for name, typ in columns)
    return f"CREATE TABLE {table} ({body})"


class FakeChatDB:
    """A temp SQLite file shaped like chat.db, with an inject() for arrivals."""

    def __init__(self, path):
        self.path = pathlib.Path(path)
        conn = sqlite3.connect(self.path)
        conn.execute(_ddl("message", MESSAGE_COLUMNS))
        conn.execute(_ddl("handle", HANDLE_COLUMNS))
        conn.commit()
        conn.close()

    def _handle_id(self, conn, handle):
        row = conn.execute("select ROWID from handle where id = ?",
                           (handle,)).fetchone()
        if row:
            return row[0]
        cur = conn.execute(
            "insert into handle (id, country, service, uncanonicalized_id) "
            "values (?, 'us', 'iMessage', ?)", (handle, handle))
        return cur.lastrowid

    def inject(self, handle, text, is_from_me=0, plain_text=False, when=None):
        """Append a row as if the message had just arrived.

        Defaults to the real-world A9 shape: text NULL, body in attributedBody.
        `plain_text=True` populates `text` instead, covering the ~1% of real
        rows that carry it.
        """
        when = time.time() if when is None else when
        date_ns = int((when - APPLE_EPOCH_OFFSET) * 1e9)
        conn = sqlite3.connect(self.path)
        try:
            hid = self._handle_id(conn, handle)
            cur = conn.execute(
                "insert into message (guid, text, handle_id, attributedBody, "
                "service, date, is_from_me, is_read, cache_has_attachments) "
                "values (?, ?, ?, ?, 'iMessage', ?, ?, 0, 0)",
                (f"fake-{date_ns}-{hid}",
                 text if plain_text else None,
                 hid,
                 None if plain_text else _typedstream(text),
                 date_ns, is_from_me))
            conn.commit()
            return cur.lastrowid
        finally:
            conn.close()
