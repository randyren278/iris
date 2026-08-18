"""CP-3.1: the fake chat.db round-trips, and the sender stub records."""
import sqlite3

from iris.chatdb import message_body
from tests.fakedb import APPLE_EPOCH_OFFSET


def query(fakedb, sql, args=()):
    conn = sqlite3.connect(f"file:{fakedb.path}?mode=ro", uri=True)
    return conn.execute(sql, args).fetchall()


def test_database_file_is_created(fakedb):
    assert fakedb.path.exists()
    tables = {r[0] for r in query(
        fakedb, "select name from sqlite_master where type='table'")}
    assert {"message", "handle"} <= tables


def test_inject_returns_increasing_rowids(fakedb):
    first = fakedb.inject("+15551234567", "one")
    second = fakedb.inject("+15551234567", "two")
    assert second > first


def test_inject_roundtrips_body_and_handle(fakedb):
    fakedb.inject("+15551234567", "hello iris")
    (text, abody, handle), = query(fakedb, (
        "select m.text, m.attributedBody, h.id from message m "
        "join handle h on h.ROWID = m.handle_id"))
    assert message_body(text, abody) == "hello iris"
    assert handle == "+15551234567"


def test_handles_are_reused_not_duplicated(fakedb):
    fakedb.inject("+15551234567", "one")
    fakedb.inject("+15551234567", "two")
    fakedb.inject("+15559999999", "three")
    assert query(fakedb, "select count(*) from handle")[0][0] == 2


def test_inbound_is_the_default(fakedb):
    fakedb.inject("+15551234567", "inbound")
    assert query(fakedb, "select is_from_me from message")[0][0] == 0


def test_outbound_is_marked(fakedb):
    fakedb.inject("+15551234567", "outbound", is_from_me=1)
    assert query(fakedb, "select is_from_me from message")[0][0] == 1


def test_dates_use_apple_epoch_nanoseconds(fakedb):
    """Real chat.db stores ns since 2001-01-01, not unix seconds."""
    fakedb.inject("+15551234567", "timed", when=APPLE_EPOCH_OFFSET + 1000)
    assert query(fakedb, "select date from message")[0][0] == 1000 * 10**9


def test_sender_records_instead_of_sending(sender):
    sender("+15551234567", "reply text")
    assert sender.sent == [("+15551234567", "reply text")]
    assert sender.last() == ("+15551234567", "reply text")
    assert sender.texts == ["reply text"]


def test_sender_starts_empty(sender):
    assert sender.sent == []
    assert sender.last() is None
