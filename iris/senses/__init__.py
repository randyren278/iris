"""Read-only, revocable source quarantine."""
from __future__ import annotations
import dataclasses, json, pathlib
@dataclasses.dataclass(frozen=True)
class SourceItem:
 source_id:str; item_id:str; starts_at:str; title:str; trust:str="untrusted"
class SenseStore:
 def __init__(self,path): self.path=pathlib.Path(path)
 def ingest_calendar(self,items):
  rows=[dataclasses.asdict(x) for x in items]
  if any(x["trust"]!="untrusted" for x in rows): raise ValueError("sources are quarantined")
  self.path.parent.mkdir(parents=True,exist_ok=True); self.path.write_text(json.dumps(rows))
 def items(self): return tuple(SourceItem(**x) for x in json.loads(self.path.read_text())) if self.path.exists() else ()
 def revoke(self,source_id): self.path.write_text(json.dumps([dataclasses.asdict(x) for x in self.items() if x.source_id!=source_id]))
class CalendarSense:
 def __init__(self,provider,store): self.provider,self.store=provider,store
 def sync(self): self.store.ingest_calendar(tuple(SourceItem("calendar",x["id"],x["starts_at"],x["title"]) for x in self.provider.list_events()))
