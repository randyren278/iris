"""Pure grammar for the explicit Iris Slack command language."""
from __future__ import annotations

import dataclasses
import re


@dataclasses.dataclass(frozen=True)
class Command:
    pass


@dataclasses.dataclass(frozen=True)
class Simple(Command):
    name: str


@dataclasses.dataclass(frozen=True)
class TextCommand(Command):
    name: str
    text: str


@dataclasses.dataclass(frozen=True)
class IndexedCommand(Command):
    name: str
    index: int
    text: str = ""


_SIMPLE = {"ls", "projects", "sessions", "link", "y", "n", "stop", "memories"}
_TEXT = {"cd", "claude", "codex", "forget", "correct"}
_INDEXED = re.compile(r"^@(\d+)\s+(.+)$")
_KILL = re.compile(r"^kill\s+(\d+)$")


def parse(text: str) -> Command | None:
    """Parse an explicit command, or return ``None`` without side effects."""
    if not isinstance(text, str):
        return None
    normalized = " ".join(text.strip().split())
    if not normalized:
        return None
    lowered = normalized.casefold()
    if lowered in _SIMPLE:
        return Simple(lowered)
    indexed = _INDEXED.fullmatch(normalized)
    if indexed:
        return IndexedCommand("session_message", int(indexed.group(1)), indexed.group(2))
    kill = _KILL.fullmatch(lowered)
    if kill:
        return IndexedCommand("kill", int(kill.group(1)))
    name, separator, remainder = normalized.partition(" ")
    if not separator or name.casefold() not in _TEXT or not remainder:
        return None
    return TextCommand(name.casefold(), remainder)
