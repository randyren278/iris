"""A9 regression: the fake must lie about `text` the way the real chat.db does.

If these fail, the fake has drifted into being easier than production and every
downstream phase is verified against a database that does not exist.
"""
import sqlite3

import pytest

from iris.chatdb import decode_attributed_body, message_body


def rows(fakedb):
    conn = sqlite3.connect(f"file:{fakedb.path}?mode=ro", uri=True)
    return conn.execute(
        "select ROWID, text, attributedBody from message order by ROWID").fetchall()


def test_injected_message_has_null_text(fakedb):
    fakedb.inject("+15551234567", "hello iris")
    (_, text, abody), = rows(fakedb)
    assert text is None, "fake populated `text`; real chat.db leaves it NULL"
    assert abody is not None


def test_production_decoder_reads_the_fakes_blob(fakedb):
    """The fake's encoder and the production decoder must agree."""
    fakedb.inject("+15551234567", "hello iris")
    (_, text, abody), = rows(fakedb)
    assert decode_attributed_body(abody) == "hello iris"
    assert message_body(text, abody) == "hello iris"


@pytest.mark.parametrize("body", [
    "x",
    "short",
    "a" * 127,                      # last single-byte length
    "b" * 128,                      # first long-form length
    "c" * 5000,                     # multi-byte long form
    "unicode: café ☕️ 日本語",       # multi-byte utf-8
    'quotes "and" \\backslashes\\',  # inert punctuation
    "line\nbreak\ttab",
])
def test_roundtrip_across_length_and_encoding_boundaries(fakedb, body):
    fakedb.inject("+15551234567", body)
    (_, text, abody), = rows(fakedb)
    assert text is None
    assert message_body(text, abody) == body


def test_plain_text_path_still_available(fakedb):
    """The ~1% of real rows that do carry `text`."""
    fakedb.inject("+15551234567", "plain one", plain_text=True)
    (_, text, abody), = rows(fakedb)
    assert text == "plain one"
    assert abody is None
    assert message_body(text, abody) == "plain one"


def test_decoder_refuses_garbage_rather_than_guessing():
    """An unrecognised layout must return None, never a wrong string."""
    assert decode_attributed_body(b"not a typedstream") is None
    assert decode_attributed_body(b"") is None
    assert decode_attributed_body(None) is None


def test_decoder_refuses_truncated_payload(fakedb):
    """A blob claiming more bytes than it carries must not return a partial.

    Truncation has to land *inside* the string payload to test this: cutting
    only the trailing dictionary leaves the body intact and decoding it in
    full is correct.
    """
    fakedb.inject("+15551234567", "abcdefghij")
    (_, _, abody), = rows(fakedb)
    blob = bytes(abody)
    cut = blob.index(b"abcdefghij") + 5  # mid-payload
    assert decode_attributed_body(blob[:cut]) is None


def test_decoder_reads_full_body_when_only_the_tail_is_lost(fakedb):
    """The complement: a payload that is intact still decodes."""
    fakedb.inject("+15551234567", "abcdefghij")
    (_, _, abody), = rows(fakedb)
    blob = bytes(abody)
    keep = blob.index(b"abcdefghij") + len("abcdefghij")
    assert decode_attributed_body(blob[:keep]) == "abcdefghij"
