"""NASA FIRMS active fire / thermal anomaly source.

FIRMS (Fire Information for Resource Management System) provides near-real-time
active fire detections from VIIRS and MODIS. We use the free **area API**:

    https://firms.modaps.eosdis.nasa.gov/api/area/csv/{MAP_KEY}/{SOURCE}/{AREA}/{DAY_RANGE}[/{DATE}]

- ``MAP_KEY``  : free key from https://firms.modaps.eosdis.nasa.gov/api/map_key/
- ``SOURCE``   : sensor product, e.g. ``VIIRS_SNPP_NRT`` (375 m, near real time)
- ``AREA``     : ``west,south,east,north`` bounding box (EPSG:4326)
- ``DAY_RANGE``: 1..10 days
- ``DATE``     : optional ``YYYY-MM-DD`` end date (defaults to most recent)

Verify the API surface before relying on it; NASA occasionally rotates product
names and the daily request quota. Docs: https://firms.modaps.eosdis.nasa.gov/api/area/

Detection model (Phase 1): raw pixel detections inside an AOI are aggregated
per acquisition date into a single *thermal* candidate event. This keeps the
per-facility timeline readable while preserving the individual pixels in the
event's ``raw`` payload for human verification. Every event is unverified and
links to the FIRMS map viewer for the AOI and date.
"""

from __future__ import annotations

import csv
import io
from collections import defaultdict
from datetime import date
from typing import Any, Optional

import requests

from ..config import AOI, firms_map_key
from ..models import Event, Provenance, utc_now_iso
from .base import Source

FIRMS_BASE = "https://firms.modaps.eosdis.nasa.gov/api/area/csv"

# Near-real-time sensor products queried by default. VIIRS first (375 m, finer
# than MODIS 1 km and better suited to facility-scale monitoring).
DEFAULT_PRODUCTS: tuple[str, ...] = (
    "VIIRS_SNPP_NRT",
    "VIIRS_NOAA20_NRT",
    "MODIS_NRT",
)

# FIRMS area API hard cap on the day-range parameter.
MAX_DAY_RANGE = 10

# Used to normalize FRP (fire radiative power, MW) into a 0..1 signal proxy.
# 50 MW is a deliberately conservative "strong thermal source" reference; the
# value is documented and easy to tune, not a calibrated threshold.
FRP_REFERENCE_MW = 50.0


def _confidence_to_float(value: str) -> float:
    """Normalize FIRMS confidence to 0..1.

    VIIRS reports ``l``/``n``/``h`` (low/nominal/high); MODIS reports 0..100.
    """
    v = (value or "").strip().lower()
    mapping = {"l": 0.3, "n": 0.6, "h": 0.9}
    if v in mapping:
        return mapping[v]
    try:
        return max(0.0, min(1.0, float(v) / 100.0))
    except ValueError:
        return 0.5


def _safe_float(value: str, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


class FirmsSource(Source):
    """Fetch and detect thermal anomalies from NASA FIRMS."""

    name = "firms"

    def __init__(
        self,
        map_key: Optional[str] = None,
        products: tuple[str, ...] = DEFAULT_PRODUCTS,
        session: Optional[requests.Session] = None,
        timeout: float = 60.0,
    ) -> None:
        self.map_key = map_key if map_key is not None else firms_map_key()
        self.products = products
        self.session = session or requests.Session()
        self.timeout = timeout

    # -- fetch --------------------------------------------------------------

    def fetch(self, aoi: AOI, since: date) -> list[dict[str, Any]]:
        """Pull raw FIRMS detections inside ``aoi`` no older than ``since``."""
        if not self.map_key:
            raise RuntimeError(
                "FIRMS_MAP_KEY is not set. Get a free key at "
                "https://firms.modaps.eosdis.nasa.gov/api/map_key/ and export "
                "it as the FIRMS_MAP_KEY environment variable."
            )

        day_range = max(1, min(MAX_DAY_RANGE, (date.today() - since).days + 1))
        area = aoi.bbox.as_firms_area()

        rows: list[dict[str, Any]] = []
        for product in self.products:
            url = f"{FIRMS_BASE}/{self.map_key}/{product}/{area}/{day_range}"
            resp = self.session.get(url, timeout=self.timeout)
            resp.raise_for_status()
            text = resp.text

            # FIRMS returns plain-text errors (not HTTP error codes) for bad
            # keys / quota; the success body is CSV with a header row.
            if not text.lstrip().lower().startswith("latitude"):
                snippet = text.strip().splitlines()[0] if text.strip() else "<empty>"
                raise RuntimeError(
                    f"FIRMS returned a non-CSV response for {product}: {snippet!r}"
                )

            for record in csv.DictReader(io.StringIO(text)):
                record["_product"] = product
                rows.append(record)

        return rows

    # -- detect -------------------------------------------------------------

    def detect(self, aoi: AOI, window: list[dict[str, Any]]) -> list[Event]:
        """Aggregate raw detections into one thermal event per acquisition date."""
        by_date: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in window:
            acq_date = (row.get("acq_date") or "").strip()
            if acq_date:
                by_date[acq_date].append(row)

        retrieved_at = utc_now_iso()
        events: list[Event] = []
        for acq_date, detections in by_date.items():
            events.append(self._build_event(aoi, acq_date, detections, retrieved_at))
        return events

    def _build_event(
        self,
        aoi: AOI,
        acq_date: str,
        detections: list[dict[str, Any]],
        retrieved_at: str,
    ) -> Event:
        lons = [_safe_float(d.get("longitude", "")) for d in detections]
        lats = [_safe_float(d.get("latitude", "")) for d in detections]
        centroid_lon = sum(lons) / len(lons)
        centroid_lat = sum(lats) / len(lats)

        # FRP column is "frp" for both VIIRS and MODIS products.
        frps = [_safe_float(d.get("frp", "")) for d in detections]
        max_frp = max(frps) if frps else 0.0
        confidences = [_confidence_to_float(d.get("confidence", "")) for d in detections]
        max_conf = max(confidences) if confidences else 0.5

        # Signal strength blends intensity (FRP) with detection confidence and
        # is clamped to 0..1. This is an OSINT *prioritization* hint, not a
        # calibrated probability of military activity.
        intensity = min(1.0, max_frp / FRP_REFERENCE_MW)
        signal_strength = round(min(1.0, 0.6 * intensity + 0.4 * max_conf), 3)

        products = sorted({str(d.get("_product", "")) for d in detections if d.get("_product")})
        notes = (
            f"{len(detections)} 件の熱異常検知（{aoi.name_ja}）。"
            f"最大FRP {max_frp:.1f} MW。"
            f"センサー: {', '.join(products) or '不明'}。"
            "自動検知の候補であり、未確認です。FIRMSの元データで確認してください。"
        )

        provenance = Provenance(
            source=self.name,
            dataset=", ".join(products) or "FIRMS",
            retrieved_at=retrieved_at,
            query=f"area={aoi.bbox.as_firms_area()} date={acq_date}",
        )

        return Event(
            id=f"firms-{aoi.id}-{acq_date}",
            aoi_id=aoi.id,
            date=acq_date,
            type="thermal",
            signal_strength=signal_strength,
            status="unverified",
            source_url=_firms_map_url(centroid_lon, centroid_lat, acq_date),
            geometry={"type": "Point", "coordinates": [centroid_lon, centroid_lat]},
            notes=notes,
            provenance=provenance,
            raw={
                "detection_count": len(detections),
                "max_frp_mw": max_frp,
                "products": products,
                "detections": [
                    {
                        "lon": _safe_float(d.get("longitude", "")),
                        "lat": _safe_float(d.get("latitude", "")),
                        "frp": _safe_float(d.get("frp", "")),
                        "acq_time": d.get("acq_time", ""),
                        "confidence": d.get("confidence", ""),
                        "daynight": d.get("daynight", ""),
                        "product": d.get("_product", ""),
                    }
                    for d in detections
                ],
            },
        )


def _firms_map_url(lon: float, lat: float, acq_date: str) -> str:
    """Deep link into the FIRMS fire map centered on the detection and date."""
    return (
        "https://firms.modaps.eosdis.nasa.gov/map/#d:"
        f"{acq_date};@{lon:.4f},{lat:.4f},10z"
    )
