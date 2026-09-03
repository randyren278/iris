"""Operator-run, bounded reachability check for the read-only web fetcher."""
from __future__ import annotations

from iris.tools.web import WebFetcher


def probe(fetcher=None) -> str:
    fetcher = fetcher or WebFetcher()
    search = fetcher.search({"query": "Iris web search probe"})
    results = search.get("results")
    if not isinstance(results, list) or not results:
        raise ValueError("search returned no results")
    result = fetcher.fetch({"url": "https://example.com/"})
    return f"Read-only web search and fetch succeeded: {len(results)} result; {result['url']}"


def main() -> int:
    try:
        print(probe())
    except (OSError, ValueError) as error:
        print(f"Read-only web probe failed: {error}")
        return 1
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
