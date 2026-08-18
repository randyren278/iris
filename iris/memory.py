"""Provenance-first durable claim storage for Iris."""
from __future__ import annotations

import dataclasses
import json
import os
import pathlib
import tempfile
import threading
import time
import uuid


@dataclasses.dataclass(frozen=True)
class MemoryRecord:
    id: str
    claim: str
    source_ref: str
    trust: str
    authoring_mode: str
    confidence: float
    created_at: float
    updated_at: float
    lifecycle: str = "active"
    supersedes: str | None = None


class MemoryPolicyError(ValueError):
    pass


class MemoryStore:
    """Append-preserving JSON ledger; only explicit trusted claims are admitted."""

    def __init__(self, path: pathlib.Path | str, *, clock=time.time, ids=lambda: uuid.uuid4().hex):
        self.path = pathlib.Path(path)
        self._clock, self._ids = clock, ids
        self._lock = threading.Lock()

    def remember(self, claim: str, *, source_ref: str, trust: str = "self",
                 authoring_mode: str = "operator_confirmed", confidence: float = 1.0,
                 supersedes: str | None = None) -> MemoryRecord:
        if trust not in {"self", "team"} or authoring_mode != "operator_confirmed":
            raise MemoryPolicyError("only explicitly confirmed self/team claims may be remembered")
        if not claim.strip() or not source_ref.strip() or not 0 <= confidence <= 1:
            raise MemoryPolicyError("claim, source reference, and confidence are required")
        with self._lock:
            records = self._load()
            if supersedes and supersedes not in self._live_ids(records):
                raise MemoryPolicyError("superseded record is not an active memory")
            now = self._clock()
            record = MemoryRecord(self._ids(), claim.strip(), source_ref.strip(), trust, authoring_mode,
                                  confidence, now, now, supersedes=supersedes)
            self._save([*records, record])
        return record

    def correct(self, record_id: str, claim: str, *, source_ref: str) -> MemoryRecord:
        return self.remember(claim, source_ref=source_ref, supersedes=record_id)

    def forget(self, record_id: str) -> MemoryRecord:
        with self._lock:
            records = self._load()
            for index, item in enumerate(records):
                if item.id == record_id:
                    tombstone = dataclasses.replace(item, lifecycle="forgotten", updated_at=self._clock())
                    records[index] = tombstone
                    self._save(records)
                    return tombstone
            raise MemoryPolicyError("memory record does not exist")

    @staticmethod
    def _live_ids(records: list[MemoryRecord]) -> set[str]:
        hidden = {item.supersedes for item in records if item.supersedes}
        return {item.id for item in records if item.lifecycle == "active" and item.id not in hidden}

    def retrieve(self, query: str = "") -> tuple[MemoryRecord, ...]:
        terms = set(query.lower().split())
        hidden = {item.supersedes for item in self._load() if item.supersedes}
        return tuple(item for item in self._load()
                     if item.lifecycle == "active" and item.id not in hidden
                     and item.trust in {"self", "team"}
                     and (not terms or terms.intersection(item.claim.lower().split())))

    def _load(self) -> list[MemoryRecord]:
        if not self.path.exists():
            return []
        return [MemoryRecord(**item) for item in json.loads(self.path.read_text())]

    def _save(self, records: list[MemoryRecord]) -> None:
        self.path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        payload = json.dumps([dataclasses.asdict(item) for item in records], sort_keys=True)
        handle, temporary = tempfile.mkstemp(dir=self.path.parent, prefix=".memory-", text=True)
        try:
            with os.fdopen(handle, "w") as stream:
                stream.write(payload)
                stream.flush()
                os.fsync(stream.fileno())
            os.chmod(temporary, 0o600)
            os.replace(temporary, self.path)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
