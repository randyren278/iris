"""Per-session serialized work lanes."""
from __future__ import annotations

import concurrent.futures
import threading


class SessionLanes:
    def __init__(self, *, max_workers: int = 8):
        self._executor = concurrent.futures.ThreadPoolExecutor(max_workers=max_workers)
        self._lock = threading.Lock()
        self._tails: dict[int, concurrent.futures.Future] = {}

    def submit(self, session_id: int, function, /, *args, **kwargs):
        with self._lock:
            previous = self._tails.get(session_id)

            def run():
                if previous is not None:
                    previous.result()
                return function(*args, **kwargs)

            future = self._executor.submit(run)
            self._tails[session_id] = future
            return future

    def shutdown(self):
        self._executor.shutdown(wait=True)
