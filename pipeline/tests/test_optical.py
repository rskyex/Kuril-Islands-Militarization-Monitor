"""Tests for the Sentinel-2 optical imagery source + store (no EE needed)."""

from __future__ import annotations

import json
from datetime import date

from pipeline.config import load_aois
from pipeline.imagery_store import ImageryStore
from pipeline.sources.optical import (
    OpticalParams,
    OpticalSource,
    SceneRef,
)


def _aoi(aoi_id: str):
    return next(a for a in load_aois() if a.id == aoi_id)


class FakeBackend:
    """Returns canned scenes and tiny PNG bytes; records thumbnail requests."""

    def __init__(self, baseline: SceneRef | None, recent: SceneRef | None):
        self._scenes = [baseline, recent]
        self._i = 0
        self.thumb_calls: list[str] = []

    def best_scene(self, aoi_geometry, start, end, params):
        scene = self._scenes[self._i] if self._i < len(self._scenes) else None
        self._i += 1
        return scene

    def thumbnail_png(self, scene_id, aoi_geometry, params):
        self.thumb_calls.append(scene_id)
        return b"\x89PNG\r\n\x1a\n" + scene_id.encode("utf-8")


def test_collect_builds_refs_and_files():
    aoi = _aoi("matua-airfield")
    backend = FakeBackend(
        baseline=SceneRef("S2/BASE", "2025-08-01", 5.0),
        recent=SceneRef("S2/RECENT", "2026-05-20", 12.0),
    )
    collected = OpticalSource(backend=backend).collect(aoi, since=date(2024, 1, 1))

    assert collected is not None
    img = collected.imagery
    assert img.aoi_id == "matua-airfield"
    assert img.baseline and img.baseline.date == "2025-08-01"
    assert img.baseline.image_url == "/api/imagery/matua-airfield/baseline.png"
    assert img.recent and img.recent.image_url == "/api/imagery/matua-airfield/recent.png"
    assert img.baseline.source_url.startswith("https://browser.dataspace.copernicus.eu/")
    assert img.provenance and img.provenance.source == "sentinel-2"

    # Two thumbnails rendered, keyed by relative path.
    assert set(collected.files) == {
        "matua-airfield/baseline.png",
        "matua-airfield/recent.png",
    }
    assert backend.thumb_calls == ["S2/BASE", "S2/RECENT"]


def test_collect_returns_none_when_no_scenes():
    aoi = _aoi("matua-airfield")
    backend = FakeBackend(baseline=None, recent=None)
    assert OpticalSource(backend=backend).collect(aoi, since=date(2024, 1, 1)) is None


def test_collect_handles_only_recent_scene():
    aoi = _aoi("etorofu-yasny")
    backend = FakeBackend(baseline=None, recent=SceneRef("S2/R", "2026-05-20", 8.0))
    collected = OpticalSource(backend=backend).collect(aoi, since=date(2024, 1, 1))
    assert collected is not None
    assert collected.imagery.baseline is None
    assert collected.imagery.recent is not None
    assert set(collected.files) == {"etorofu-yasny/recent.png"}


def test_imagery_store_writes_files_and_index(tmp_path):
    aoi = _aoi("matua-airfield")
    backend = FakeBackend(
        baseline=SceneRef("S2/BASE", "2025-08-01", 5.0),
        recent=SceneRef("S2/RECENT", "2026-05-20", 12.0),
    )
    collected = OpticalSource(backend=backend).collect(aoi, since=date(2024, 1, 1))
    assert collected is not None

    store = ImageryStore(
        index_path=tmp_path / "imagery.json", imagery_dir=tmp_path / "imagery"
    )
    store.save(collected)

    # Thumbnail files written.
    assert (tmp_path / "imagery" / "matua-airfield" / "baseline.png").exists()
    assert (tmp_path / "imagery" / "matua-airfield" / "recent.png").exists()

    # Index upserted by AOI id.
    index = json.loads((tmp_path / "imagery.json").read_text(encoding="utf-8"))
    assert "matua-airfield" in index["aois"]
    assert index["aois"]["matua-airfield"]["recent"]["cloud_pct"] == 12.0

    # A second AOI is added without dropping the first (idempotent upsert).
    aoi2 = _aoi("etorofu-yasny")
    backend2 = FakeBackend(None, SceneRef("S2/R2", "2026-05-21", 9.0))
    collected2 = OpticalSource(backend=backend2).collect(aoi2, since=date(2024, 1, 1))
    assert collected2 is not None
    store.save(collected2)
    index2 = json.loads((tmp_path / "imagery.json").read_text(encoding="utf-8"))
    assert set(index2["aois"]) == {"matua-airfield", "etorofu-yasny"}


def test_default_params_are_sane():
    p = OpticalParams()
    assert 0 < p.max_cloud_pct <= 100
    assert p.thumb_dimensions >= 128
