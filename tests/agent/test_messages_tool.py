import sqlite3
from datetime import datetime, timezone

import pytest

import iris.tools.messages as messages_module
from iris.tools.messages import (
    MessagesSearch,
    _sent_at,
    decode_attributed_body,
    validate_messages_arguments,
)


APPLE_EPOCH = datetime(2001, 1, 1, tzinfo=timezone.utc)


def archived(text):
    raw = text.encode()
    return b"typedstream NSString\x01\x94\x84\x01+" + bytes([len(raw)]) + raw


def apple_nanoseconds(iso):
    value = datetime.fromisoformat(iso)
    return int((value - APPLE_EPOCH).total_seconds() * 1_000_000_000)


def messages_database(path):
    connection = sqlite3.connect(path)
    connection.executescript(
        """
        create table message (
            ROWID integer primary key,
            text text,
            attributedBody blob,
            date integer,
            is_from_me integer,
            handle_id integer
        );
        create table handle (ROWID integer primary key, id text);
        create table chat (ROWID integer primary key, display_name text, chat_identifier text);
        create table chat_message_join (chat_id integer, message_id integer);
        """
    )
    connection.execute("insert into handle values (1, 'lauren@example.com')")
    connection.execute("insert into handle values (2, '+15555550100')")
    connection.execute("insert into chat values (1, null, 'lauren@example.com')")
    connection.execute("insert into chat values (2, 'Lauren Kate Yu', 'group-1')")
    connection.execute(
        "insert into message values (1, ?, null, ?, 0, 1)",
        ("Lauren said hello", apple_nanoseconds("2026-08-01T10:00:00+00:00")),
    )
    connection.execute(
        "insert into message values (2, null, ?, ?, 1, 2)",
        (archived("Dinner on Friday"), apple_nanoseconds("2026-08-02T10:00:00+00:00")),
    )
    connection.execute(
        "insert into message values (3, 'unrelated', null, ?, 0, 2)",
        (apple_nanoseconds("2026-08-03T10:00:00+00:00"),),
    )
    connection.execute("insert into message values (4, null, null, null, 0, 2)")
    connection.execute("insert into message values (5, 'other topic', null, 1, 0, 2)")
    connection.execute("insert into message values (6, 'Lauren invalid date', null, null, 0, 1)")
    connection.execute("insert into chat_message_join values (1, 1)")
    connection.execute("insert into chat_message_join values (2, 2)")
    connection.execute("insert into chat_message_join values (2, 3)")
    connection.commit()
    connection.close()


def test_messages_search_matches_body_or_conversation_and_returns_bounded_context(tmp_path):
    path = tmp_path / "chat.db"
    messages_database(path)

    result = MessagesSearch(path).search({"query": "Lauren"})

    assert result == {
        "query": "Lauren",
        "matches": [
            {
                "conversation": "Lauren Kate Yu",
                "direction": "received",
                "sent_at": "2026-08-03T10:00:00+00:00",
                "text": "unrelated",
            },
            {
                "conversation": "Lauren Kate Yu",
                "direction": "sent",
                "sent_at": "2026-08-02T10:00:00+00:00",
                "text": "Dinner on Friday",
            },
            {
                "conversation": "lauren@example.com",
                "direction": "received",
                "sent_at": "2026-08-01T10:00:00+00:00",
                "text": "Lauren said hello",
            },
        ],
    }


def test_attributed_body_decoder_fails_closed_on_unknown_or_truncated_archives():
    assert decode_attributed_body(None) is None
    assert decode_attributed_body(b"unknown") is None
    assert decode_attributed_body(b"NSString\x01\x94\x84\x01+\x05no") is None
    assert decode_attributed_body(b"NSString\x01\x94\x84\x01+\x81\x02\x00\xff\xff") is None
    assert decode_attributed_body(b"NSString\x01\x94\x84\x01+") is None
    assert decode_attributed_body(b"NSString\x01\x94\x84\x01+\x81\x02") is None
    assert decode_attributed_body(b"NSString\x01\x94\x84\x01+\x84") is None


def test_messages_timestamp_decoder_supports_seconds_and_fails_closed():
    assert _sent_at(0) == "2001-01-01T00:00:00+00:00"
    assert _sent_at("not a timestamp") is None
    assert _sent_at(10**30) is None


def test_messages_arguments_are_strict_trimmed_and_bounded():
    assert validate_messages_arguments({"query": "  Lauren  "}) == {"query": "Lauren"}
    assert len(validate_messages_arguments({"query": "x" * 300})["query"]) == 200
    for arguments in ({}, {"query": ""}, {"query": 4}, {"query": "x", "limit": 2}):
        with pytest.raises(ValueError, match="query is required"):
            validate_messages_arguments(arguments)


def test_messages_search_requires_the_expected_read_only_database_schema(tmp_path):
    missing = tmp_path / "missing.db"
    with pytest.raises(RuntimeError, match="Messages database is unavailable"):
        MessagesSearch(missing).search({"query": "Lauren"})

    wrong = tmp_path / "wrong.db"
    sqlite3.connect(wrong).close()
    with pytest.raises(RuntimeError, match="Messages database is unavailable"):
        MessagesSearch(wrong).search({"query": "Lauren"})


def test_messages_search_opens_sqlite_in_read_only_mode(monkeypatch, tmp_path):
    path = tmp_path / "chat.db"
    messages_database(path)
    real_connect = sqlite3.connect
    calls = []

    def connect(database, **kwargs):
        calls.append((database, kwargs))
        return real_connect(database, **kwargs)

    monkeypatch.setattr(messages_module.sqlite3, "connect", connect)
    MessagesSearch(path).search({"query": "Lauren"})

    assert calls == [(f"file:{path}?mode=ro", {"uri": True, "timeout": 2})]


def test_messages_search_stops_at_its_result_cap(tmp_path):
    path = tmp_path / "chat.db"
    messages_database(path)
    result = MessagesSearch(path, max_results=1).search({"query": "Lauren"})
    assert len(result["matches"]) == 1
