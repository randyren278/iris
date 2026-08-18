from iris.senses import CalendarSense, SenseStore, SourceItem


class Fake:
    def list_events(self):
        return [{"id": "e1", "starts_at": "2026-08-20T10:00:00", "title": "Meeting"}]


def test_ingesting_one_source_preserves_other_sources_already_quarantined(tmp_path):
    store = SenseStore(tmp_path / "senses.json")
    store.ingest_calendar((SourceItem("tasks", "b", "t", "Buy milk"),))
    CalendarSense(Fake(), store).sync()
    source_ids = {item.source_id for item in store.items()}
    assert source_ids == {"tasks", "calendar"}
