"""Small HTTPS-only web research primitives with bounded, public fetches."""
from __future__ import annotations

import html.parser
import ipaddress
import socket
from urllib.parse import urlencode, urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener


MAX_BYTES = 64_000


def _public_host(host: str, resolver=socket.getaddrinfo) -> None:
    if not host:
        raise ValueError("URL host is required")
    try:
        addresses = resolver(host, None, type=socket.SOCK_STREAM)
    except socket.gaierror as error:
        raise ValueError("host could not be resolved") from error
    if not addresses:
        raise ValueError("host could not be resolved")
    for address in addresses:
        if not ipaddress.ip_address(address[4][0]).is_global:
            raise ValueError("non-public hosts are not allowed")


def validate_fetch_arguments(arguments: dict[str, object]) -> dict[str, object]:
    if set(arguments) != {"url"} or not isinstance(arguments["url"], str):
        raise ValueError("URL is required")
    parsed = urlparse(arguments["url"])
    if parsed.scheme != "https" or parsed.username or parsed.password:
        raise ValueError("only HTTPS URLs are allowed")
    return arguments


def validate_search_arguments(arguments: dict[str, object]) -> dict[str, object]:
    if set(arguments) != {"query"} or not isinstance(arguments["query"], str) or not arguments["query"].strip():
        raise ValueError("query is required")
    return {"query": arguments["query"].strip()[:200]}


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *_args):
        return None


class WebFetcher:
    def __init__(self, *, resolver=socket.getaddrinfo, opener=None, timeout: float = 8.0):
        self._resolver = resolver
        self._opener = opener or build_opener(_NoRedirect())
        self._timeout = timeout

    def fetch(self, arguments: dict[str, object]) -> dict[str, object]:
        url = str(arguments["url"])
        _public_host(urlparse(url).hostname or "", self._resolver)
        request = Request(url, headers={"User-Agent": "Iris read-only research"})
        with self._opener.open(request, timeout=self._timeout) as response:
            return {"url": response.geturl(), "text": response.read(MAX_BYTES + 1).decode("utf-8", "replace")[:MAX_BYTES]}

    def search(self, arguments: dict[str, object]) -> dict[str, object]:
        url = "https://html.duckduckgo.com/html/?" + urlencode({"q": arguments["query"]})
        document = self.fetch({"url": url})["text"]
        parser = _SearchResults()
        parser.feed(document)
        return {"query": arguments["query"], "results": parser.results[:8]}


class _SearchResults(html.parser.HTMLParser):
    def __init__(self):
        super().__init__()
        self.results: list[dict[str, str]] = []
        self._href: str | None = None
        self._text: list[str] = []

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        if tag == "a" and "result__a" in values.get("class", ""):
            self._href, self._text = values.get("href", ""), []

    def handle_data(self, data):
        if self._href is not None:
            self._text.append(data)

    def handle_endtag(self, tag):
        if tag == "a" and self._href is not None:
            title = "".join(self._text).strip()
            if title:
                self.results.append({"title": title, "url": self._href})
            self._href = None
