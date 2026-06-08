"""Event store.

Phase 1 uses a simple, dependency-free JSON document at ``data/events.json``.
The store is upsert-by-id so the pipeline is idempotent: re-running over the
same window replaces matching events rather than duplicating them. (PostGIS /
SQLite can be swapped in behind this same interface later.)
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Iterable

from .config import EVENTS_PATH
from .models import Event


def _load_raw(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8") as fh:
        data = json.load(fh)
    if isinstance(data, dict) and "events" in data:
        return list(data["events"])
    if isinstance(data, list):
        return data
    raise ValueError(f"Unrecognized event store format in {path}")


def _atomic_write(path: Path, payload: str) -> None:
    """Write atomically so a crashed run never leaves a truncated store."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(payload)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


class EventStore:
    """JSON-backed, upsert-by-id event store."""

    def __init__(self, path: Path = EVENTS_PATH) -> None:
        self.path = path

    def all(self) -> list[dict]:
        return _load_raw(self.path)

    def upsert(self, events: Iterable[Event]) -> int:
        """Insert or replace events by ``id``. Returns count written.

        Existing events whose ids are not in ``events`` are preserved, so
        re-running a single source does not wipe other sources' events.
        """
        existing = {e["id"]: e for e in self.all()}
        written = 0
        for ev in events:
            existing[ev.id] = ev.to_dict()
            written += 1

        merged = sorted(existing.values(), key=lambda e: (e.get("date", ""), e["id"]))
        payload = json.dumps(merged, ensure_ascii=False, indent=2, sort_keys=True)
        _atomic_write(self.path, payload)
        return written
