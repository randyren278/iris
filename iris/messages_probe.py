"""Operator-run probe for bounded, read-only Messages history search."""
from __future__ import annotations

import pathlib

from iris.tools.messages import MessagesSearch


def probe(search=None, *, query="the") -> str:
    search = search or MessagesSearch(pathlib.Path.home() / "Library/Messages/chat.db")
    result = search.search({"query": query})
    return f"Messages read-only search succeeded: {len(result['matches'])} matching message(s)."


def main() -> int:
    try:
        print(probe())
    except (RuntimeError, ValueError) as error:
        print(f"Messages read-only search failed: {error}")
        return 1
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
