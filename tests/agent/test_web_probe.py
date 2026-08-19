from iris.web_probe import probe


def test_web_probe_reports_only_the_final_url():
    class Fetcher:
        def fetch(self, arguments):
            assert arguments == {"url": "https://example.com/"}
            return {"url": "https://example.com/", "text": "private source content"}
    assert probe(Fetcher()) == "Read-only web probe succeeded: https://example.com/"
