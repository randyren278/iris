import pytest

from iris.web_probe import probe


def test_web_probe_requires_search_and_fetch_to_succeed_without_leaking_content():
    class Fetcher:
        def search(self, arguments):
            assert arguments == {"query": "Iris web search probe"}
            return {"query": arguments["query"], "results": [
                {"title": "Example", "url": "https://example.com/"},
            ]}

        def fetch(self, arguments):
            assert arguments == {"url": "https://example.com/"}
            return {"url": "https://example.com/", "text": "private source content"}

    assert probe(Fetcher()) == (
        "Read-only web search and fetch succeeded: 1 result; https://example.com/"
    )


def test_web_probe_fails_when_search_silently_returns_no_results():
    class Fetcher:
        def search(self, _arguments):
            return {"query": "probe", "results": []}

    with pytest.raises(ValueError, match="search returned no results"):
        probe(Fetcher())
