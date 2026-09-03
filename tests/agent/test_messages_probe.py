from iris.messages_probe import probe


def test_messages_probe_reports_only_match_count_not_private_content():
    class Search:
        def search(self, arguments):
            assert arguments == {"query": "probe"}
            return {"query": "probe", "matches": [
                {"conversation": "private", "text": "private body"},
                {"conversation": "private", "text": "another private body"},
            ]}

    assert probe(Search(), query="probe") == (
        "Messages read-only search succeeded: 2 matching message(s)."
    )
