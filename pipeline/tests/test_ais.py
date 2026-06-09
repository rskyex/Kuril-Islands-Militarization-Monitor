"""Tests for the AIS naval-activity source (no network / websockets needed)."""

from __future__ import annotations

from datetime import date

from pipeline.config import load_aois
from pipeline.sources.ais import AisSource


def _aoi(aoi_id: str):
    return next(a for a in load_aois() if a.id == aoi_id)


class FakeAisBackend:
    """Returns canned position reports; records the bbox it was asked for."""

    def __init__(self, reports):
        self.reports = reports
        self.calls: list[tuple] = []

    def collect_positions(self, west, south, east, north, listen_seconds):
        self.calls.append((west, south, east, north, listen_seconds))
        return self.reports


def _report(mmsi, ts, lat=44.965, lon=147.672, sog=0.0, name="", ship_type=""):
    return {
        "mmsi": mmsi,
        "lat": lat,
        "lon": lon,
        "sog": sog,
        "timestamp": ts,
        "name": name,
        "ship_type": ship_type,
    }


def test_fetch_passes_bbox_and_returns_reports():
    aoi = _aoi("etorofu-kasatka")
    backend = FakeAisBackend([_report(123, "2026-06-08T01:00:00Z")])
    src = AisSource(backend=backend, listen_seconds=30)
    rows = src.fetch(aoi, since=date(2026, 1, 1))

    assert len(rows) == 1
    b = aoi.bbox
    assert backend.calls == [(b.west, b.south, b.east, b.north, 30)]


def test_detect_groups_by_mmsi():
    aoi = _aoi("etorofu-kasatka")
    window = [
        _report(111, "2026-06-08T01:00:00Z", sog=0.2, name="ALPHA", ship_type="Cargo"),
        _report(111, "2026-06-08T01:05:00Z", sog=0.3, name="ALPHA", ship_type="Cargo"),
        _report(222, "2026-06-08T01:02:00Z", sog=14.0, name="BRAVO"),
    ]
    events = AisSource(backend=FakeAisBackend(window)).detect(aoi, window)
    by_id = {e.id: e for e in events}

    assert set(by_id) == {
        "ais-etorofu-kasatka-111-2026-06-08",
        "ais-etorofu-kasatka-222-2026-06-08",
    }
    a = by_id["ais-etorofu-kasatka-111-2026-06-08"]
    assert a.type == "naval"
    assert a.status == "unverified"
    assert a.raw["report_count"] == 2
    assert a.raw["mmsi"] == 111
    assert a.source_url.endswith("mmsi:111")
    assert len(a.raw["track"]) == 2
    assert 0.0 <= a.signal_strength <= 1.0


def test_slow_persistent_scores_higher_than_fast_transit():
    aoi = _aoi("etorofu-kasatka")
    slow = [_report(1, f"2026-06-08T01:0{i}:00Z", sog=0.1) for i in range(6)]
    fast = [_report(2, "2026-06-08T01:00:00Z", sog=18.0)]
    e_slow = AisSource(backend=FakeAisBackend(slow)).detect(aoi, slow)[0]
    e_fast = AisSource(backend=FakeAisBackend(fast)).detect(aoi, fast)[0]
    assert e_slow.signal_strength > e_fast.signal_strength


def test_detect_ids_are_stable():
    aoi = _aoi("etorofu-kasatka")
    window = [_report(999, "2026-06-08T01:00:00Z")]
    src = AisSource(backend=FakeAisBackend(window))
    ids1 = {e.id for e in src.detect(aoi, window)}
    ids2 = {e.id for e in src.detect(aoi, window)}
    assert ids1 == ids2
