"""Thread-bound Slack notifications for approvals and runtime notices."""
from __future__ import annotations

import threading


class OriginThreadNotifier:
    """Delivers asynchronous notices only to the latest allowed DM thread."""

    def __init__(self, client):
        self.client = client
        self._target = None
        self._lock = threading.Lock()

    def observe(self, message) -> None:
        with self._lock:
            self._target = (message.channel_id, message.reply_thread_ts)

    def notify(self, text: str) -> bool:
        with self._lock:
            target = self._target
        if target is None:
            return False
        self.client.post_message(channel_id=target[0], thread_ts=target[1], text=text)
        return True
