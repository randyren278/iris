import socket

import pytest

from iris.tools.web import (
    MAX_BYTES,
    WebFetcher,
    _NoRedirect,
    _RssSearchResults,
    _public_host,
    validate_fetch_arguments,
    validate_search_arguments,
)


def resolver_for(*addresses):
    return lambda _host, _port, **_kwargs: [
        (socket.AF_INET6 if ":" in address else socket.AF_INET, socket.SOCK_STREAM, 6, "", (address, 0))
        for address in addresses
    ]


def test_public_host_requires_resolvable_globally_routable_addresses():
    with pytest.raises(ValueError, match="URL host is required"):
        _public_host("")

    def broken(*_args, **_kwargs):
        raise socket.gaierror("dns")

    with pytest.raises(ValueError, match="host could not be resolved"):
        _public_host("example.com", broken)
    with pytest.raises(ValueError, match="host could not be resolved"):
        _public_host("example.com", lambda *_args, **_kwargs: [])

    for address in ("127.0.0.1", "10.0.0.1", "169.254.1.2", "::1", "fc00::1"):
        with pytest.raises(ValueError, match="non-public hosts"):
            _public_host("example.com", resolver_for(address))

    _public_host("example.com", resolver_for("1.1.1.1", "2606:4700:4700::1111"))


def test_fetch_argument_validation_is_https_only_and_credential_free():
    assert validate_fetch_arguments({"url": "https://example.com/path?q=1"}) == {
        "url": "https://example.com/path?q=1"
    }
    for arguments in (
        {},
        {"url": 3},
        {"url": "http://example.com"},
        {"url": "https://user@example.com"},
        {"url": "https://user:pass@example.com"},
        {"url": "https://example.com", "extra": True},
    ):
        with pytest.raises(ValueError):
            validate_fetch_arguments(arguments)


def test_search_argument_validation_trims_and_bounds_query():
    assert validate_search_arguments({"query": "  iris agent  "}) == {"query": "iris agent"}
    assert len(validate_search_arguments({"query": "x" * 300})["query"]) == 200
    for arguments in ({}, {"query": ""}, {"query": "   "}, {"query": 4}, {"query": "x", "extra": 1}):
        with pytest.raises(ValueError, match="query is required"):
            validate_search_arguments(arguments)


def test_redirect_handler_refuses_redirects():
    assert _NoRedirect().redirect_request(None, None, None, None, None, None) is None


class Response:
    def __init__(self, body, *, url="https://example.com/final"):
        self.body = body
        self.url = url

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def geturl(self):
        return self.url

    def read(self, amount):
        assert amount == MAX_BYTES + 1
        return self.body


class Opener:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def open(self, request, *, timeout):
        self.calls.append((request, timeout))
        return self.response


def test_fetch_checks_public_host_sets_user_agent_and_caps_payload():
    opener = Opener(Response(("é" + "x" * (MAX_BYTES + 20)).encode()))
    fetcher = WebFetcher(resolver=resolver_for("1.1.1.1"), opener=opener, timeout=4.5)
    result = fetcher.fetch({"url": "https://example.com/path"})

    assert result["url"] == "https://example.com/final"
    assert len(result["text"]) <= MAX_BYTES
    request, timeout = opener.calls[0]
    assert request.full_url == "https://example.com/path"
    assert request.get_header("User-agent") == "Iris read-only research"
    assert timeout == 4.5


def test_fetch_replaces_invalid_utf8_in_provider_data():
    opener = Opener(Response(b"hello\xffworld"))
    result = WebFetcher(resolver=resolver_for("8.8.8.8"), opener=opener).fetch({"url": "https://example.com"})
    assert result["text"] == "hello�world"


def test_general_search_uses_structured_feed_parses_titles_and_caps_results(monkeypatch):
    items = "".join(
        f'<item><title>Result {index}</title><link>https://example.com/{index}</link></item>'
        for index in range(10)
    )
    document = "<rss><channel>" + items + "</channel></rss>"
    fetcher = WebFetcher()
    seen = []

    def fake_fetch(arguments):
        seen.append(arguments)
        return {"text": document}

    monkeypatch.setattr(fetcher, "fetch", fake_fetch)
    result = fetcher.search({"query": "iris agent"})

    assert seen == [{"url": "https://www.bing.com/search?format=rss&q=iris+agent"}]
    assert result["query"] == "iris agent"
    assert len(result["results"]) == 8
    assert result["results"][0] == {"title": "Result 0", "url": "https://example.com/0"}


def test_search_parser_ignores_data_outside_an_rss_item():
    parser = _RssSearchResults()
    parser.feed(
        "<title>channel</title><rss><channel><item><title>hello world</title>"
        "<link>https://e</link></item></channel></rss>"
    )
    assert parser.results == [{"title": "hello world", "url": "https://e"}]


def test_news_search_uses_google_news_structured_feed(monkeypatch):
    rss = (
        "<rss><channel><item><title>Manila story</title>"
        "<link>https://news.example/story</link></item></channel></rss>"
    )
    fetcher = WebFetcher()
    seen = []

    def fake_fetch(arguments):
        seen.append(arguments)
        return {"text": rss}

    monkeypatch.setattr(fetcher, "fetch", fake_fetch)

    assert fetcher.search({"query": "latest news in Manila"}) == {
        "query": "latest news in Manila",
        "results": [{"title": "Manila story", "url": "https://news.example/story"}],
    }
    assert seen == [
        {"url": "https://news.google.com/rss/search?hl=en-CA&gl=CA&ceid=CA:en&q=latest+news+in+Manila"},
    ]


def test_news_search_falls_back_to_independent_feed_when_google_response_is_invalid(monkeypatch):
    rss = (
        "<rss><channel><title>Search</title><item>"
        "<title>Manila update</title><link>https://news.example/update</link>"
        "</item></channel></rss>"
    )
    fetcher = WebFetcher()
    documents = iter(("<html>not a feed</html>", rss))
    seen = []

    def fake_fetch(arguments):
        seen.append(arguments)
        return {"text": next(documents)}

    monkeypatch.setattr(fetcher, "fetch", fake_fetch)

    result = fetcher.search({"query": "Manila news"})

    assert result["results"] == [
        {"title": "Manila update", "url": "https://news.example/update"}
    ]
    assert seen[-1] == {"url": "https://www.bing.com/search?format=rss&q=Manila+news"}


def test_search_distinguishes_no_matches_from_invalid_provider_responses(monkeypatch):
    fetcher = WebFetcher()
    monkeypatch.setattr(
        fetcher, "fetch", lambda _arguments: {"text": "<rss><channel></channel></rss>"}
    )
    assert fetcher.search({"query": "no such page"}) == {
        "query": "no such page", "results": []
    }

    monkeypatch.setattr(fetcher, "fetch", lambda _arguments: {"text": "<html>blocked</html>"})
    with pytest.raises(ValueError, match="invalid responses"):
        fetcher.search({"query": "no such page"})


def test_search_parser_drops_incomplete_or_unsafe_result_links():
    parser = _RssSearchResults()
    parser.feed(
        "<rss><channel>"
        "<item><title>HTTP</title><link>http://example.com</link></item>"
        "<item><title>No host</title><link>https:///missing</link></item>"
        "<item><title>Credentials</title><link>https://user@example.com</link></item>"
        "<item><link>https://example.com/no-title</link></item>"
        "</channel></rss>"
    )
    assert parser.results == []
