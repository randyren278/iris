"""CP-3.2: the poller yields newly arrived inbound messages."""
import pytest

from iris.poller import Poller


@pytest.fixture
def poller(fakedb, tmp_path):
    p = Poller(fakedb.path, tmp_path / "state.json")
    p.poll_once()  # first call establishes the high-water mark
    return p


def test_yields_injected_message(fakedb, poller):
    fakedb.inject("+15551234567", "hello iris")
    (msg,) = poller.poll_once()
    assert msg.body == "hello iris"
    assert msg.handle == "+15551234567"


def test_body_comes_from_attributedbody(fakedb, poller):
    """The A9 path: text is NULL, so this only works via the decoder."""
    fakedb.inject("+15551234567", "decoded body")
    (msg,) = poller.poll_once()
    assert msg.body == "decoded body"


def test_plain_text_rows_also_yield(fakedb, poller):
    fakedb.inject("+15551234567", "plain body", plain_text=True)
    (msg,) = poller.poll_once()
    assert msg.body == "plain body"


def test_message_is_not_yielded_twice(fakedb, poller):
    fakedb.inject("+15551234567", "once")
    assert len(poller.poll_once()) == 1
    assert poller.poll_once() == []


def test_empty_when_nothing_arrives(poller):
    assert poller.poll_once() == []


def test_yields_in_arrival_order(fakedb, poller):
    for n in ("first", "second", "third"):
        fakedb.inject("+15551234567", n)
    assert [m.body for m in poller.poll_once()] == ["first", "second", "third"]


def test_multiple_senders_are_distinguished(fakedb, poller):
    fakedb.inject("+15551234567", "from a")
    fakedb.inject("+15559999999", "from b")
    got = {(m.handle, m.body) for m in poller.poll_once()}
    assert got == {("+15551234567", "from a"), ("+15559999999", "from b")}


def test_first_run_does_not_replay_history(fakedb, tmp_path):
    """A fresh poller must not treat existing history as newly arrived."""
    for n in range(5):
        fakedb.inject("+15551234567", f"old {n}")
    fresh = Poller(fakedb.path, tmp_path / "fresh.json")
    assert fresh.poll_once() == []
    fakedb.inject("+15551234567", "new one")
    assert [m.body for m in fresh.poll_once()] == ["new one"]


def test_opens_database_read_only(fakedb, poller):
    """A write through the poller's own connection must be refused."""
    import sqlite3
    conn = poller._connect()
    with pytest.raises(sqlite3.OperationalError):
        conn.execute("insert into message (guid) values ('nope')")


def test_undecodable_row_is_skipped_not_fatal(fakedb, poller):
    """A row Iris cannot read must not stall the loop or crash it."""
    import sqlite3
    conn = sqlite3.connect(fakedb.path)
    conn.execute("insert into message (guid, text, handle_id, attributedBody, "
                 "date, is_from_me) values ('junk', NULL, 1, ?, 0, 0)",
                 (b"not a typedstream",))
    conn.commit()
    conn.close()
    fakedb.inject("+15551234567", "readable")
    assert [m.body for m in poller.poll_once()] == ["readable"]


def test_message_repr_does_not_leak_the_body(fakedb, poller):
    """repr() is the default stringification reached for in debugging/logging;
    it must not print raw message content, per CLAUDE.md's no-verbatim-logging rule."""
    fakedb.inject("+15551234567", "very private content nobody should log")
    (msg,) = poller.poll_once()
    assert "very private content nobody should log" not in repr(msg)
