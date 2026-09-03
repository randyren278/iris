"""Small HTTPS-only web research primitives with bounded, public fetches."""
from __future__ import annotations

import html.parser
import ipaddress
import re
import socket
from urllib.parse import urlencode, urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener


MAX_BYTES = 64_000
NEWS_SEARCH_ENDPOINT = "https://news.google.com/rss/search?hl=en-CA&gl=CA&ceid=CA:en"
GENERAL_SEARCH_ENDPOINT = "https://www.bing.com/search?format=rss"
_NEWS_QUERY = re.compile(r"\b(?:news|latest|breaking|today|current events?)\b", re.IGNORECASE)


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
        reachable = 0
        endpoints = (
            (NEWS_SEARCH_ENDPOINT, GENERAL_SEARCH_ENDPOINT)
            if _NEWS_QUERY.search(str(arguments["query"]))
            else (GENERAL_SEARCH_ENDPOINT, NEWS_SEARCH_ENDPOINT)
        )
        for endpoint in endpoints:
            url = endpoint + "&" + urlencode({"q": arguments["query"]})
            document = self.fetch({"url": url})["text"]
            if "<rss" not in document or "<channel" not in document:
                continue
            reachable += 1
            parser = _RssSearchResults()
            parser.feed(document)
            if parser.results:
                return {"query": arguments["query"], "results": parser.results[:8]}
        if not reachable:
            raise ValueError("search providers returned invalid responses")
        return {"query": arguments["query"], "results": []}


def _result_url(href: str) -> str | None:
    parsed = urlparse(href)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        return None
    return href


class _RssSearchResults(html.parser.HTMLParser):
    def __init__(self):
        super().__init__()
        self.results: list[dict[str, str]] = []
        self._item: dict[str, str] | None = None
        self._field: str | None = None
        self._text: list[str] = []

    def handle_starttag(self, tag, _attrs):
        if tag == "item":
            self._item = {}
        elif self._item is not None and tag in {"title", "link"}:
            self._field, self._text = tag, []

    def handle_data(self, data):
        if self._field is not None:
            self._text.append(data)

    def handle_endtag(self, tag):
        if self._item is not None and tag == self._field:
            self._item[tag] = "".join(self._text).strip()
            self._field = None
        elif tag == "item" and self._item is not None:
            url = _result_url(self._item.get("link", ""))
            title = self._item.get("title", "")
            if title and url:
                self.results.append({"title": title, "url": url})
            self._item = None
