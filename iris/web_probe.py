"""Operator-run, bounded reachability check for the read-only web fetcher."""
from __future__ import annotations

from iris.tools.web import WebFetcher


def probe(fetcher=None) -> str:
    result = (fetcher or WebFetcher()).fetch({"url": "https://example.com/"})
    return f"Read-only web probe succeeded: {result['url']}"


def main() -> int:
    try:
        print(probe())
    except (OSError, ValueError) as error:
        print(f"Read-only web probe failed: {error}")
        return 1
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
