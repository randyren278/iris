"""Bounded consequential-action policy."""
from __future__ import annotations
import dataclasses
@dataclasses.dataclass(frozen=True)
class Capability:
 name:str; requires_approval:bool=True
class CapabilityPolicy:
 def __init__(self, allowed=()): self._allowed=set(allowed)
 def request(self,name,approved):
  if name not in self._allowed: return False
  return approved is True
