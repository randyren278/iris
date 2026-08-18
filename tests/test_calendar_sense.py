from iris.senses import CalendarSense, SenseStore
class Fake:
 def list_events(self): return [{"id":"e1","starts_at":"2026-08-20T10:00:00","title":"Private meeting"}]
def test_fake_calendar_is_ingested_as_quarantined_metadata(tmp_path):
 store=SenseStore(tmp_path/"senses.json"); CalendarSense(Fake(),store).sync()
 assert store.items()[0].trust == "untrusted"
