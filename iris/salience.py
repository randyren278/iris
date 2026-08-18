"""Explainable shadow-mode nudge scoring."""
from __future__ import annotations
import dataclasses
@dataclasses.dataclass(frozen=True)
class Candidate:
 text:str; score:int; explanation:tuple[str,...]; source:str
class SalienceEngine:
 def __init__(self, *, shadow=True): self.shadow=shadow; self.candidates=[]
 def mute(self): self.shadow=True
 def feedback(self, candidate, helpful): return dataclasses.replace(candidate, score=candidate.score+(1 if helpful else -1))
 def score(self, *, deadline_hours=None, conflict=False, project_recent=False, source="calendar"):
  reasons=[]; value=0
  if deadline_hours is not None and deadline_hours<=24: value+=3; reasons.append("deadline within 24 hours")
  if conflict: value+=2; reasons.append("calendar conflict")
  if project_recent: value+=1; reasons.append("recent project activity")
  candidate=Candidate("Potentially helpful reminder",value,tuple(reasons),source); self.candidates.append(candidate); return candidate
 def notify(self, candidate, send):
  if self.shadow: return False
  send(candidate.text); return True
