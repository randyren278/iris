"""Bounded, read-only search over the operator's local Messages database."""
from __future__ import annotations

import pathlib
import re
import sqlite3
from contextlib import closing
from datetime import datetime, timedelta, timezone
from urllib.parse import quote


APPLE_EPOCH = datetime(2001, 1, 1, tzinfo=timezone.utc)
MAX_RESULTS = 20
MAX_SNIPPET = 500
_PAYLOAD = re.compile(rb"NSString\x01.\x84\x01\+", re.S)


def validate_messages_arguments(arguments: dict[str, object]) -> dict[str, object]:
    if set(arguments) != {"query"} or not isinstance(arguments["query"], str) or not arguments["query"].strip():
        raise ValueError("query is required")
    return {"query": arguments["query"].strip()[:200]}


def decode_attributed_body(blob: bytes | None) -> str | None:
    """Decode only the NSString payload from Apple's typedstream archive."""
    if not blob or (match := _PAYLOAD.search(blob)) is None:
        return None
    index = match.end()
    if index >= len(blob):
        return None
    length, index = blob[index], index + 1
    widths = {0x81: 2, 0x82: 3, 0x83: 4}
    if length in widths:
        width = widths[length]
        if index + width > len(blob):
            return None
        length = int.from_bytes(blob[index:index + width], "little")
        index += width
    elif length >= 0x80:
        return None
    raw = blob[index:index + length]
    if len(raw) != length:
        return None
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return None


def _sent_at(raw: object) -> str | None:
    if not isinstance(raw, (int, float)):
        return None
    seconds = raw / 1_000_000_000 if abs(raw) > 10_000_000_000 else raw
    try:
        return (APPLE_EPOCH + timedelta(seconds=seconds)).isoformat()
    except OverflowError:
        return None


class MessagesSearch:
    def __init__(self, path: pathlib.Path | str, *, max_results: int = MAX_RESULTS):
        self.path = pathlib.Path(path).expanduser()
        self.max_results = max_results

    def search(self, arguments: dict[str, object]) -> dict[str, object]:
        query = str(arguments["query"])
        needle = query.casefold()
        uri = "file:" + quote(str(self.path.resolve()), safe="/") + "?mode=ro"
        matches = []
        try:
            with closing(sqlite3.connect(uri, uri=True, timeout=2)) as connection:
                connection.execute("pragma query_only = on")
                rows = connection.execute(
                    """
                    select m.text, m.attributedBody, m.date, m.is_from_me,
                           coalesce(c.display_name, c.chat_identifier, h.id, 'Unknown')
                    from message as m
                    left join handle as h on h.ROWID = m.handle_id
                    left join chat_message_join as cmj on cmj.message_id = m.ROWID
                    left join chat as c on c.ROWID = cmj.chat_id
                    group by m.ROWID
                    order by m.ROWID desc
                    """
                )
                for text, archive, date, is_from_me, conversation in rows:
                    body = text if isinstance(text, str) else decode_attributed_body(archive)
                    if not body:
                        continue
                    body = re.sub(r"\s+", " ", body).strip()
                    conversation = conversation.strip() if isinstance(conversation, str) else "Unknown"
                    if needle not in body.casefold() and needle not in conversation.casefold():
                        continue
                    sent_at = _sent_at(date)
                    if sent_at is None:
                        continue
                    matches.append({
                        "conversation": conversation or "Unknown",
                        "direction": "sent" if bool(is_from_me) else "received",
                        "sent_at": sent_at,
                        "text": body[:MAX_SNIPPET],
                    })
                    if len(matches) >= self.max_results:
                        break
        except (OSError, sqlite3.Error) as error:
            raise RuntimeError("Messages database is unavailable for read-only search") from error
        return {"query": query, "matches": matches}
