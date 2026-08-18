"""Privacy-preserving append-only audit records."""
from __future__ import annotations

import hashlib
import json
import pathlib
import threading
import time


class AuditLog:
    def __init__(self, path: pathlib.Path | str, *, max_bytes: int = 1_000_000):
        self.path = pathlib.Path(path)
        self.max_bytes = max_bytes
        self._lock = threading.Lock()

    def append(self, event: str, **metadata) -> None:
        record = {"at": time.time(), "event": event, **metadata}
        encoded = json.dumps(record, sort_keys=True) + "\n"
        with self._lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            if self.path.exists() and self.path.stat().st_size + len(encoded.encode()) > self.max_bytes:
                rotated = self.path.with_suffix(self.path.suffix + ".1")
                if rotated.exists():
                    rotated.unlink()
                self.path.replace(rotated)
            with self.path.open("a", encoding="utf-8") as stream:
                stream.write(encoded)

    @staticmethod
    def rejected_inbound(*, event_id: str, user_id: str, body: str) -> dict:
        return {"event_id": event_id, "user_id": user_id,
                "body_sha256": hashlib.sha256(body.encode()).hexdigest()}
