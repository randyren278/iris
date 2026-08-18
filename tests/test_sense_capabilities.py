from iris.senses import SenseStore, SourceItem
def test_only_quarantined_readonly_source_items_are_accepted(tmp_path):
 store=SenseStore(tmp_path/"s.json"); store.ingest_calendar((SourceItem("calendar","a","t","x"),))
 assert store.items()[0].source_id == "calendar"
