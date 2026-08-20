import socket

import pytest

from iris.tools.web import (
    MAX_BYTES,
    WebFetcher,
    _NoRedirect,
    _SearchResults,
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


def test_search_builds_duckduckgo_query_parses_titles_and_caps_results(monkeypatch):
    anchors = "".join(
        f'<a class="result__a other" href="https://example.com/{index}"> Result <b>{index}</b> </a>'
        for index in range(10)
    )
    document = (
        '<a class="unrelated" href="https://ignore.example">ignore</a>'
        '<a class="result__a" href="https://blank.example">   </a>'
        + anchors
    )
    fetcher = WebFetcher()
    seen = []

    def fake_fetch(arguments):
        seen.append(arguments)
        return {"text": document}

    monkeypatch.setattr(fetcher, "fetch", fake_fetch)
    result = fetcher.search({"query": "iris agent"})

    assert seen == [{"url": "https://html.duckduckgo.com/html/?q=iris+agent"}]
    assert result["query"] == "iris agent"
    assert len(result["results"]) == 8
    assert result["results"][0] == {"title": "Result 0", "url": "https://example.com/0"}


def test_search_parser_ignores_data_outside_active_result_link():
    parser = _SearchResults()
    parser.feed("prefix<a class='result__a' href='https://e'>hello<span> world</span></a>suffix")
    assert parser.results == [{"title": "hello world", "url": "https://e"}]
