"""Read-only, revocable source quarantine."""
from __future__ import annotations
import dataclasses, json, pathlib

@dataclasses.dataclass(frozen=True)
class SourceItem:
    source_id: str
    item_id: str
    starts_at: str
    title: str
    trust: str = "untrusted"

class SenseStore:
    def __init__(self, path): self.path = pathlib.Path(path)
    def ingest_calendar(self, items):
        records = [dataclasses.asdict(item) for item in items]
        if any(item["trust"] != "untrusted" for item in records): raise ValueError("sources are quarantined")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(records))
    def items(self):
        return tuple(SourceItem(**item) for item in json.loads(self.path.read_text())) if self.path.exists() else ()
    def revoke(self, source_id):
        retained = [dataclasses.asdict(item) for item in self.items() if item.source_id != source_id]
        self.path.write_text(json.dumps(retained))

class CalendarSense:
    def __init__(self, provider, store): self.provider, self.store = provider, store
    def sync(self):
        self.store.ingest_calendar(tuple(SourceItem("calendar", item["id"], item["starts_at"], item["title"])
                                         for item in self.provider.list_events()))
