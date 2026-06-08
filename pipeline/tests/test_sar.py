"""Tests for the Sentinel-1 SAR source.

These exercise the pure detection / windowing logic with a fake backend, so no
Earth Engine install or credentials are needed. The real EeBackend.compute_change
is excluded from coverage (it requires live EE) but is kept thin and importable.
"""

from __future__ import annotations

from datetime import date

from pipeline.config import load_aois
from pipeline.sources.sar import (
    ChangePatch,
    ChangeResult,
    SarParams,
    SarSource,
    SarWindows,
    _geometry_centroid,
    _patch_event_id,
)


def _aoi(aoi_id: str):
    return next(a for a in load_aois() if a.id == aoi_id)


class FakeBackend:
    """Records the call and returns canned patches."""

    def __init__(self, patches):
        self.patches = patches
        self.calls: list[tuple] = []

    def compute_change(self, aoi_geometry, windows: SarWindows, params: SarParams) -> ChangeResult:
        self.calls.append((aoi_geometry, windows, params))
        return ChangeResult(
            patches=self.patches,
            baseline_scene_count=12,
            recent_scene_count=3,
            polarization=params.polarization,
            orbit_pass=params.orbit_pass,
        )


def _patch(mean_db: float, lon=153.255, lat=48.051, area=12_000.0) -> ChangePatch:
    geom = {
        "type": "Polygon",
        "coordinates": [[
            [lon - 0.002, lat - 0.002],
            [lon + 0.002, lat - 0.002],
            [lon + 0.002, lat + 0.002],
            [lon - 0.002, lat + 0.002],
            [lon - 0.002, lat - 0.002],
        ]],
    }
    return ChangePatch(geometry=geom, centroid=(lon, lat), mean_change_db=mean_db, area_m2=area)


def test_windows_respect_since_floor():
    src = SarSource(backend=FakeBackend([]), recent_days=24, baseline_days=180)
    today = date(2026, 6, 8)
    # since well before the baseline span -> baseline_start = recent_start - 180d
    w = src.windows(since=date(2024, 1, 1), today=today)
    assert w.recent_end == "2026-06-08"
    assert w.recent_start == "2026-05-15"  # 24 days before
    assert w.baseline_end == "2026-05-15"
    assert w.baseline_start == "2025-11-16"  # 180 days before baseline_end

    # since after that floor clamps the baseline start.
    w2 = src.windows(since=date(2026, 3, 1), today=today)
    assert w2.baseline_start == "2026-03-01"


def test_fetch_threads_meta_and_serializes():
    aoi = _aoi("matua-airfield")
    backend = FakeBackend([_patch(5.0)])
    src = SarSource(backend=backend)
    rows = src.fetch(aoi, since=date(2025, 1, 1))

    assert len(rows) == 1
    row = rows[0]
    assert row["mean_change_db"] == 5.0
    assert row["geometry"]["type"] == "Polygon"
    assert row["_meta"]["recent_scene_count"] == 3
    assert row["_meta"]["polarization"] == "VV"
    assert "windows" in row["_meta"]
    # backend received the AOI geometry and computed windows
    assert backend.calls and backend.calls[0][0] == aoi.geometry


def test_detect_increase_is_construction_decrease_is_clearance():
    aoi = _aoi("matua-airfield")
    backend = FakeBackend([_patch(6.0), _patch(-7.0, lon=153.260)])
    src = SarSource(backend=backend)
    events = src.detect(aoi, src.fetch(aoi, since=date(2025, 1, 1)))

    by_type = {e.type for e in events}
    assert by_type == {"construction", "clearance"}
    for e in events:
        assert e.status == "unverified"
        assert e.aoi_id == "matua-airfield"
        assert 0.0 <= e.signal_strength <= 1.0
        assert e.geometry["type"] == "Polygon"
        assert e.source_url.startswith("https://browser.dataspace.copernicus.eu/")
        assert e.provenance is not None and e.provenance.source == "sentinel-1"


def test_detect_event_ids_are_stable():
    aoi = _aoi("matua-airfield")
    src = SarSource(backend=FakeBackend([_patch(6.0)]))
    ids1 = {e.id for e in src.detect(aoi, src.fetch(aoi, since=date(2025, 1, 1)))}
    ids2 = {e.id for e in src.detect(aoi, src.fetch(aoi, since=date(2025, 1, 1)))}
    assert ids1 == ids2
    assert all(i.startswith("s1-matua-airfield-") for i in ids1)


def test_patch_id_distinguishes_direction():
    inc = _patch_event_id("matua-airfield", "2026-06-08", 153.255, 48.051, True)
    dec = _patch_event_id("matua-airfield", "2026-06-08", 153.255, 48.051, False)
    assert inc != dec


def test_geometry_centroid_polygon():
    lon, lat = _geometry_centroid(
        {"type": "Polygon", "coordinates": [[[0, 0], [2, 0], [2, 2], [0, 2], [0, 0]]]}
    )
    # mean of the 5 ring vertices (first == last) -> (0.8, 0.8)
    assert round(lon, 3) == 0.8
    assert round(lat, 3) == 0.8
