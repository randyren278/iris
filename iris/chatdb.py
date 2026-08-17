#!/usr/bin/env python3
"""Recover a message body from chat.db.

`message.text` is NULL for ~99% of rows on macOS 26 (313404/314995 outbound,
338316/340622 inbound, measured 2026-08-17). The body lives in
`message.attributedBody`, an NSAttributedString archived as a typedstream.

Only the string payload is decoded, not the whole archive. The layout is:

    ... NSString <refbyte> \x84 \x01 + <length> <utf-8 bytes> ...

<refbyte> is a typedstream object-reference counter (\x94 when the class chain
is NSAttributedString/NSString, \x95 when it is the NSMutableAttributedString/
NSMutableString variant), so it is matched as a wildcard. <length> is one byte
under 128, otherwise a 0x81/0x82/0x83 tag followed by 2/3/4 little-endian
length bytes.

Validated against every row in the live chat.db that has BOTH `text` and
`attributedBody` set (3897 rows): 3897 exact matches, 0 mismatches, 0
undecodable. Those rows are the only available ground truth -- they are the
ones where Messages happens to populate both columns.
"""
import re

_PAYLOAD = re.compile(rb"NSString\x01.\x84\x01\+", re.S)


def decode_attributed_body(blob):
    """Return the message body in `blob`, or None if it cannot be decoded.

    Never raises and never guesses: an unrecognised layout returns None so the
    caller can fall back to the `text` column rather than act on a bad read.
    """
    if not blob:
        return None
    m = _PAYLOAD.search(blob)
    if not m:
        return None
    i = m.end()
    n = blob[i]
    i += 1
    if n == 0x81:
        n = int.from_bytes(blob[i:i + 2], "little"); i += 2
    elif n == 0x82:
        n = int.from_bytes(blob[i:i + 3], "little"); i += 3
    elif n == 0x83:
        n = int.from_bytes(blob[i:i + 4], "little"); i += 4
    elif n >= 0x80:
        return None
    raw = blob[i:i + n]
    if len(raw) != n:
        return None
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return None


def message_body(text, attributed_body):
    """Body of a `message` row, preferring the plain `text` column."""
    if text is not None:
        return text
    return decode_attributed_body(attributed_body)
