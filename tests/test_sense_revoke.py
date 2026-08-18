from iris.senses import SenseStore, SourceItem
def test_revoke_purges_only_the_requested_source(tmp_path):
 store=SenseStore(tmp_path/"senses.json"); store.ingest_calendar((SourceItem("calendar","a","t","x"),SourceItem("tasks","b","t","y")))
 store.revoke("calendar"); assert [x.source_id for x in store.items()] == ["tasks"]
