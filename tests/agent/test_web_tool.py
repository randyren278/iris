import socket

import pytest

from iris.tools.web import WebFetcher, _public_host, validate_fetch_arguments


def test_fetch_rejects_non_https_and_non_public_targets():
    with pytest.raises(ValueError):
        validate_fetch_arguments({"url": "http://example.com"})
    with pytest.raises(ValueError):
        _public_host("internal", lambda *_args, **_kwargs: [(None, None, None, None, ("127.0.0.1", 0))])


def test_fetch_is_bounded_and_uses_resolved_public_host():
    class Response:
        def __enter__(self): return self
        def __exit__(self, *_args): return False
        def geturl(self): return "https://example.com/"
        def read(self, _size): return b"hello"
    class Opener:
        def open(self, request, timeout):
            assert request.full_url == "https://example.com/"
            assert timeout == 3
            return Response()
    fetcher = WebFetcher(opener=Opener(), timeout=3,
                         resolver=lambda *_args, **_kwargs: [(None, None, None, None, ("93.184.216.34", 0))])
    assert fetcher.fetch({"url": "https://example.com/"}) == {"url": "https://example.com/", "text": "hello"}
