"""Inspectable operator model with separated evidence origins."""
from __future__ import annotations
import dataclasses, time
@dataclasses.dataclass(frozen=True)
class ModelEntry:
 id:str; value:str; origin:str; confidence:float; created_at:float; deleted:bool=False
class UserModel:
 def __init__(self, clock=time.time): self._clock=clock; self._entries=[]
 def add(self,id,value,origin,confidence):
  if origin not in {"stated","observed","inferred"}: raise ValueError("invalid origin")
  if origin=="inferred" and confidence>0.7: raise ValueError("inferences are bounded")
  entry=ModelEntry(id,value,origin,confidence,self._clock()); self._entries.append(entry); return entry
 def inspect(self): return tuple(x for x in self._entries if not x.deleted)
 def explain(self,id):
  entry=next(x for x in self._entries if x.id==id)
  return f"{entry.origin} entry at confidence {entry.confidence}: {entry.value}"
 def decay(self, now):
  self._entries=[dataclasses.replace(x, confidence=x.confidence*0.5) if x.origin=="inferred" and not x.deleted else x for x in self._entries]
 def delete(self,id):
  for i,x in enumerate(self._entries):
   if x.id==id: self._entries[i]=dataclasses.replace(x,deleted=True); return
  raise KeyError(id)
