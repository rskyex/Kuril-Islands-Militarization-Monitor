"""Tests for the FIRMS source detection logic (no network required)."""

from __future__ import annotations

from pipeline.config import load_aois
from pipeline.sources.firms import FirmsSource, _confidence_to_float


def _aoi(aoi_id: str):
    return next(a for a in load_aois() if a.id == aoi_id)


def test_confidence_mapping():
    assert _confidence_to_float("h") == 0.9
    assert _confidence_to_float("n") == 0.6
    assert _confidence_to_float("l") == 0.3
    assert _confidence_to_float("80") == 0.8
    assert _confidence_to_float("") == 0.5  # unknown -> neutral


def test_detect_aggregates_by_date():
    aoi = _aoi("matua-airfield")
    lon, lat = aoi.center
    window = [
        {
            "latitude": str(lat),
            "longitude": str(lon),
            "acq_date": "2026-06-01",
            "acq_time": "0112",
            "frp": "12.5",
            "confidence": "h",
            "daynight": "N",
            "_product": "VIIRS_SNPP_NRT",
        },
        {
            "latitude": str(lat + 0.01),
            "longitude": str(lon + 0.01),
            "acq_date": "2026-06-01",
            "acq_time": "0113",
            "frp": "40.0",
            "confidence": "n",
            "daynight": "N",
            "_product": "VIIRS_SNPP_NRT",
        },
        {
            "latitude": str(lat),
            "longitude": str(lon),
            "acq_date": "2026-06-03",
            "acq_time": "0200",
            "frp": "5.0",
            "confidence": "l",
            "daynight": "D",
            "_product": "MODIS_NRT",
        },
    ]

    events = FirmsSource(map_key="dummy").detect(aoi, window)
    by_id = {e.id: e for e in events}

    # Two distinct acquisition dates -> two aggregated events.
    assert set(by_id) == {
        "firms-matua-airfield-2026-06-01",
        "firms-matua-airfield-2026-06-03",
    }

    day1 = by_id["firms-matua-airfield-2026-06-01"]
    assert day1.type == "thermal"
    assert day1.status == "unverified"
    assert day1.raw["detection_count"] == 2
    assert day1.raw["max_frp_mw"] == 40.0
    assert 0.0 <= day1.signal_strength <= 1.0
    assert day1.source_url.startswith("https://firms.modaps.eosdis.nasa.gov/map/")
    assert day1.geometry["type"] == "Point"
    assert day1.provenance is not None
    assert day1.provenance.source == "firms"


def test_detect_is_idempotent_on_ids():
    aoi = _aoi("matua-airfield")
    lon, lat = aoi.center
    row = {
        "latitude": str(lat),
        "longitude": str(lon),
        "acq_date": "2026-06-01",
        "frp": "10",
        "confidence": "h",
        "_product": "VIIRS_SNPP_NRT",
    }
    src = FirmsSource(map_key="dummy")
    ids_first = {e.id for e in src.detect(aoi, [row])}
    ids_second = {e.id for e in src.detect(aoi, [row])}
    assert ids_first == ids_second
