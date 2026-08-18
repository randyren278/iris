"""Fail-closed natural-language fallback that produces proposals only."""
from __future__ import annotations

import dataclasses
import time

from iris.grammar import Command, parse


@dataclasses.dataclass(frozen=True)
class Proposal:
    command: Command
    created_at: float
    expires_at: float


class FallbackTranslator:
    """Validate a no-tools translator result; never execute it."""

    def __init__(self, translator, *, clock=time.monotonic, ttl_seconds: float = 60.0):
        self._translator = translator
        self._clock = clock
        self._ttl_seconds = ttl_seconds
        self._proposal: Proposal | None = None

    def propose(self, text: str) -> Proposal | None:
        raw = self._translator(text)
        if not isinstance(raw, dict) or set(raw) != {"command"} or not isinstance(raw["command"], str):
            return None
        command = parse(raw["command"])
        if command is None:
            return None
        now = self._clock()
        self._proposal = Proposal(command, now, now + self._ttl_seconds)
        return self._proposal

    def confirm(self) -> Command | None:
        proposal = self._proposal
        self._proposal = None
        if proposal is None or self._clock() > proposal.expires_at:
            return None
        return proposal.command

    def discard(self) -> None:
        self._proposal = None
