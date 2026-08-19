"""Expose only already-quarantined, opt-in sense records as read-only data."""
from __future__ import annotations

from iris.senses import SenseStore


def validate_sense_arguments(arguments: dict[str, object]) -> dict[str, object]:
    if arguments:
        raise ValueError("sense listing takes no arguments")
    return {}


class QuarantinedSenseReader:
    def __init__(self, store: SenseStore):
        self._store = store

    def __call__(self, _arguments: dict[str, object]) -> list[dict[str, str]]:
        return [{"source_id": item.source_id, "item_id": item.item_id,
                 "starts_at": item.starts_at, "title": item.title,
                 "trust": item.trust} for item in self._store.items()]
