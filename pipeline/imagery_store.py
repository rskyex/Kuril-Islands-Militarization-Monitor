"""Imagery store for Sentinel-2 clear-day context (Phase 3).

Persists rendered thumbnails under ``data/imagery/<aoi>/...`` and an index at
``data/imagery.json`` (upsert by AOI id, so the pipeline stays idempotent and
re-running one AOI does not drop others). The web app reads the index and
serves the thumbnails via an API route.
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from .config import DATA_DIR
from .sources.optical import CollectedImagery

IMAGERY_DIR = DATA_DIR / "imagery"
IMAGERY_INDEX = DATA_DIR / "imagery.json"


def _atomic_write_bytes(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(payload)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def _atomic_write_text(path: Path, payload: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(payload)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


class ImageryStore:
    """JSON index + thumbnail files for per-AOI optical imagery."""

    def __init__(self, index_path: Path = IMAGERY_INDEX, imagery_dir: Path = IMAGERY_DIR) -> None:
        self.index_path = index_path
        self.imagery_dir = imagery_dir

    def _load_index(self) -> dict:
        if not self.index_path.exists():
            return {"schema_version": 1, "aois": {}}
        with self.index_path.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
        data.setdefault("aois", {})
        return data

    def save(self, collected: CollectedImagery) -> None:
        """Write thumbnail files and upsert the AOI's index entry."""
        for rel_path, payload in collected.files.items():
            _atomic_write_bytes(self.imagery_dir / rel_path, payload)

        index = self._load_index()
        index["aois"][collected.imagery.aoi_id] = collected.imagery.to_dict()
        _atomic_write_text(
            self.index_path,
            json.dumps(index, ensure_ascii=False, indent=2, sort_keys=True),
        )
