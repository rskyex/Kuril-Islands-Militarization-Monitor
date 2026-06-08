"""Sentinel-1 (C-band SAR) backscatter change detection — PHASE 2.

SAR is the monitor's primary sensor: it sees through cloud and polar night,
which matters at Kuril latitudes. This module compares a recent backscatter
composite against an earlier baseline over each AOI and flags areas of
significant change as *unverified* construction / clearance candidates, each
linked back to the underlying Sentinel-1 scene.

Design for testability and offline import
-----------------------------------------
All Earth Engine interaction is isolated behind :class:`SarBackend` (a
``Protocol``). The real implementation, :class:`EeBackend`, imports
``earthengine-api`` *lazily* inside its methods, so:

- ``import pipeline.sources.sar`` works with no Earth Engine installed (the
  rest of the pipeline and the unit tests do not need it);
- the pure detection logic (:meth:`SarSource.detect`) is unit-tested by
  feeding it plain dicts;
- the fetch + windowing logic is unit-tested by injecting a fake backend.

Running it for real (locally)
-----------------------------
Earth Engine needs Google credentials, which are not available in CI / the
build sandbox. To run live:

    pip install -r pipeline/requirements-sar.txt
    earthengine authenticate                 # one-time, opens a browser
    export EE_PROJECT=your-gcp-project-id     # Cloud project for EE
    python -m pipeline.run --source sentinel-1 --days 240

Or use a service account by setting ``GOOGLE_APPLICATION_CREDENTIALS`` to its
JSON key path and ``EE_SERVICE_ACCOUNT`` to its email.

Backscatter change model
------------------------
``COPERNICUS/S1_GRD`` in Earth Engine is calibrated, terrain-corrected sigma0
in decibels. We build a median composite over the baseline window and another
over the recent window (restricted to one polarization and one orbit pass so
the imaging geometry is comparable), smooth both to suppress speckle, and take
the dB difference. Pixels whose |change| exceeds a threshold are vectorized
into patches. A backscatter *increase* (new hard / angular structures, large
equipment) is flagged ``construction``; a *decrease* (cleared, smoothed ground)
is flagged ``clearance``. None of this is confirmation — every patch is an
unverified candidate for a human to check against the linked imagery.
"""

from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any, Optional, Protocol

from ..config import AOI
from ..models import Event, Provenance, utc_now_iso
from .base import Source

S1_COLLECTION = "COPERNICUS/S1_GRD"

# Normalization references for signal_strength (documented, tunable — not
# calibrated thresholds). A patch at/above these is treated as "strong".
CHANGE_DB_REFERENCE = 8.0       # dB difference
AREA_REFERENCE_M2 = 20_000.0    # ~0.02 km^2


@dataclass(frozen=True)
class SarParams:
    """Tunable detection parameters for the Sentinel-1 change routine."""

    polarization: str = "VV"          # VV is most consistent for land change.
    orbit_pass: str = "DESCENDING"    # Restrict to one pass for comparable geometry.
    change_threshold_db: float = 3.0  # |recent - baseline| dB to count as change.
    smoothing_radius_m: float = 50.0  # Speckle-suppression focal-mean radius.
    min_area_m2: float = 5_000.0      # Drop change patches smaller than this.
    reduce_scale_m: float = 20.0      # Vectorization scale (S1 GRD pixel ~10 m).


@dataclass(frozen=True)
class SarWindows:
    """Baseline vs recent date windows (ISO ``YYYY-MM-DD``)."""

    baseline_start: str
    baseline_end: str
    recent_start: str
    recent_end: str


@dataclass(frozen=True)
class ChangePatch:
    """One vectorized region of significant backscatter change."""

    geometry: dict[str, Any]            # GeoJSON Polygon / MultiPolygon
    centroid: tuple[float, float]       # (lon, lat)
    mean_change_db: float               # signed mean dB change over the patch
    area_m2: float


@dataclass(frozen=True)
class ChangeResult:
    """Output of a backscatter-change computation over one AOI."""

    patches: list[ChangePatch]
    baseline_scene_count: int
    recent_scene_count: int
    polarization: str
    orbit_pass: str
    collection: str = S1_COLLECTION


class SarBackend(Protocol):
    """Pluggable backend that performs the SAR change computation.

    Implemented for real by :class:`EeBackend`; replaced by a fake in tests.
    """

    def compute_change(
        self,
        aoi_geometry: dict[str, Any],
        windows: SarWindows,
        params: SarParams,
    ) -> ChangeResult: ...


# --------------------------------------------------------------------------
# Source
# --------------------------------------------------------------------------


class SarSource(Source):
    """Sentinel-1 backscatter change-detection source."""

    name = "sentinel-1"

    def __init__(
        self,
        backend: Optional[SarBackend] = None,
        params: SarParams = SarParams(),
        recent_days: int = 24,
        baseline_days: int = 180,
    ) -> None:
        # ``backend=None`` defers to a real EeBackend, created on first fetch so
        # importing/constructing the source never requires Earth Engine.
        self._backend = backend
        self.params = params
        self.recent_days = recent_days
        self.baseline_days = baseline_days

    @property
    def backend(self) -> SarBackend:
        if self._backend is None:
            self._backend = EeBackend()
        return self._backend

    def windows(self, since: date, today: Optional[date] = None) -> SarWindows:
        """Derive baseline/recent windows, using ``since`` as a baseline floor.

        recent  = [today - recent_days, today]
        baseline = [max(since, recent_start - baseline_days), recent_start]
        """
        today = today or date.today()
        recent_start = today - timedelta(days=self.recent_days)
        baseline_end = recent_start
        baseline_start = max(since, baseline_end - timedelta(days=self.baseline_days))
        return SarWindows(
            baseline_start=baseline_start.isoformat(),
            baseline_end=baseline_end.isoformat(),
            recent_start=recent_start.isoformat(),
            recent_end=today.isoformat(),
        )

    # -- fetch --------------------------------------------------------------

    def fetch(self, aoi: AOI, since: date) -> list[dict[str, Any]]:
        """Run the backscatter-change computation and return raw patch records."""
        windows = self.windows(since)
        result = self.backend.compute_change(aoi.geometry, windows, self.params)

        meta = {
            "collection": result.collection,
            "polarization": result.polarization,
            "orbit_pass": result.orbit_pass,
            "baseline_scene_count": result.baseline_scene_count,
            "recent_scene_count": result.recent_scene_count,
            "windows": {
                "baseline_start": windows.baseline_start,
                "baseline_end": windows.baseline_end,
                "recent_start": windows.recent_start,
                "recent_end": windows.recent_end,
            },
        }

        return [
            {
                "geometry": p.geometry,
                "centroid": [p.centroid[0], p.centroid[1]],
                "mean_change_db": p.mean_change_db,
                "area_m2": p.area_m2,
                "_meta": meta,
            }
            for p in result.patches
        ]

    # -- detect -------------------------------------------------------------

    def detect(self, aoi: AOI, window: list[dict[str, Any]]) -> list[Event]:
        """Turn raw change patches into unverified candidate events."""
        retrieved_at = utc_now_iso()
        events: list[Event] = []
        for rec in window:
            events.append(self._build_event(aoi, rec, retrieved_at))
        return events

    def _build_event(
        self, aoi: AOI, rec: dict[str, Any], retrieved_at: str
    ) -> Event:
        meta = rec.get("_meta", {})
        windows = meta.get("windows", {})
        recent_start = windows.get("recent_start", "")
        recent_end = windows.get("recent_end", "")

        mean_db = float(rec.get("mean_change_db", 0.0))
        area_m2 = float(rec.get("area_m2", 0.0))
        centroid = rec.get("centroid", [0.0, 0.0])
        lon, lat = float(centroid[0]), float(centroid[1])

        increase = mean_db >= 0.0
        event_type = "construction" if increase else "clearance"

        magnitude = min(1.0, abs(mean_db) / CHANGE_DB_REFERENCE)
        area_term = min(1.0, area_m2 / AREA_REFERENCE_M2)
        signal_strength = round(min(1.0, 0.7 * magnitude + 0.3 * area_term), 3)

        direction_ja = "増加（建設・新設の可能性）" if increase else "減少（地表改変・撤去の可能性）"
        notes = (
            f"Sentinel-1 後方散乱の変化を検出（{aoi.name_ja}）。"
            f"平均変化 {mean_db:+.1f} dB、面積 約{area_m2/10000:.2f} ha、後方散乱{direction_ja}。"
            f"基準期間 {windows.get('baseline_start','?')}〜{windows.get('baseline_end','?')} と "
            f"直近期間 {recent_start}〜{recent_end} の比較。"
            f"偏波 {meta.get('polarization','?')}／{meta.get('orbit_pass','?')}。"
            "自動検知の未確認候補です。元のSAR画像で確認してください。"
        )

        provenance = Provenance(
            source=self.name,
            dataset=f"{meta.get('collection', S1_COLLECTION)} {meta.get('polarization','')} {meta.get('orbit_pass','')}".strip(),
            retrieved_at=retrieved_at,
            query=(
                f"baseline={windows.get('baseline_start','?')}..{windows.get('baseline_end','?')} "
                f"recent={recent_start}..{recent_end}"
            ),
        )

        return Event(
            id=_patch_event_id(aoi.id, recent_end, lon, lat, increase),
            aoi_id=aoi.id,
            date=recent_end or date.today().isoformat(),
            type=event_type,
            signal_strength=signal_strength,
            status="unverified",
            source_url=_eo_browser_url(lon, lat, recent_start, recent_end),
            geometry=rec.get("geometry", {"type": "Point", "coordinates": [lon, lat]}),
            notes=notes,
            provenance=provenance,
            raw={
                "mean_change_db": mean_db,
                "area_m2": area_m2,
                "centroid": [lon, lat],
                "direction": "increase" if increase else "decrease",
                "baseline_scene_count": meta.get("baseline_scene_count"),
                "recent_scene_count": meta.get("recent_scene_count"),
            },
        )


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------


def _patch_event_id(aoi_id: str, recent_end: str, lon: float, lat: float, increase: bool) -> str:
    """Stable, idempotent id for a change patch (same change -> same id)."""
    direction = "inc" if increase else "dec"
    key = f"{aoi_id}|{recent_end}|{lon:.4f}|{lat:.4f}|{direction}"
    digest = hashlib.sha1(key.encode("utf-8")).hexdigest()[:10]
    return f"s1-{aoi_id}-{recent_end}-{digest}"


def _eo_browser_url(lon: float, lat: float, from_date: str, to_date: str) -> str:
    """Deep link into the Copernicus Data Space EO Browser at the S1 scene.

    Lets a human pull the underlying Sentinel-1 imagery over the AOI/window
    for verification — free, no account needed to view.
    """
    return (
        "https://browser.dataspace.copernicus.eu/?"
        f"zoom=13&lat={lat:.4f}&lng={lon:.4f}"
        f"&fromTime={from_date}T00%3A00%3A00.000Z"
        f"&toTime={to_date}T23%3A59%3A59.999Z"
        "&datasetId=S1_CDAS_IW_GRD"
    )


def _geometry_centroid(geometry: dict[str, Any]) -> tuple[float, float]:
    """Rough centroid (mean of exterior vertices) of a Polygon/MultiPolygon."""
    coords: list[list[float]] = []
    gtype = geometry.get("type")
    raw = geometry.get("coordinates", [])
    if gtype == "Polygon" and raw:
        coords = list(raw[0])
    elif gtype == "MultiPolygon":
        for poly in raw:
            if poly:
                coords.extend(poly[0])
    elif gtype == "Point":
        return float(raw[0]), float(raw[1])
    if not coords:
        return 0.0, 0.0
    lon = sum(c[0] for c in coords) / len(coords)
    lat = sum(c[1] for c in coords) / len(coords)
    return lon, lat


# --------------------------------------------------------------------------
# Real Earth Engine backend (lazy-imports earthengine-api)
# --------------------------------------------------------------------------


class EeBackend:
    """Earth Engine implementation of :class:`SarBackend`.

    ``earthengine-api`` is imported lazily so this module stays importable
    without it. Credentials come from a prior ``earthengine authenticate`` plus
    ``EE_PROJECT``, or from a service account via ``GOOGLE_APPLICATION_CREDENTIALS``
    and ``EE_SERVICE_ACCOUNT``.
    """

    def __init__(self, project: Optional[str] = None) -> None:
        self.project = project or os.environ.get("EE_PROJECT") or None
        self._initialized = False

    def _ee(self):  # returns the ee module, initialized.
        try:
            import ee  # type: ignore
        except ImportError as exc:  # pragma: no cover - depends on optional dep
            raise RuntimeError(
                "earthengine-api is not installed. Install it with "
                "`pip install -r pipeline/requirements-sar.txt` to run the "
                "Sentinel-1 source."
            ) from exc

        if not self._initialized:
            sa_email = os.environ.get("EE_SERVICE_ACCOUNT")
            key_file = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
            if sa_email and key_file:
                creds = ee.ServiceAccountCredentials(sa_email, key_file)
                ee.Initialize(creds, project=self.project)
            else:
                ee.Initialize(project=self.project)
            self._initialized = True
        return ee

    def _collection(self, ee, geom, params: SarParams, start: str, end: str):
        return (
            ee.ImageCollection(S1_COLLECTION)
            .filterBounds(geom)
            .filterDate(start, end)
            .filter(ee.Filter.eq("instrumentMode", "IW"))
            .filter(ee.Filter.listContains("transmitterReceiverPolarisation", params.polarization))
            .filter(ee.Filter.eq("orbitProperties_pass", params.orbit_pass))
            .select(params.polarization)
        )

    def compute_change(
        self,
        aoi_geometry: dict[str, Any],
        windows: SarWindows,
        params: SarParams,
    ) -> ChangeResult:  # pragma: no cover - requires Earth Engine credentials
        ee = self._ee()
        geom = ee.Geometry(aoi_geometry)

        base_col = self._collection(ee, geom, params, windows.baseline_start, windows.baseline_end)
        rec_col = self._collection(ee, geom, params, windows.recent_start, windows.recent_end)

        base_n = int(base_col.size().getInfo())
        rec_n = int(rec_col.size().getInfo())
        if base_n == 0 or rec_n == 0:
            # Not enough coverage to compare; emit no candidates this run.
            return ChangeResult([], base_n, rec_n, params.polarization, params.orbit_pass)

        kernel = ee.Kernel.circle(radius=params.smoothing_radius_m, units="meters")
        base = base_col.median().focal_mean(kernel=kernel)
        rec = rec_col.median().focal_mean(kernel=kernel)
        diff = rec.subtract(base).rename("change_db")

        significant = diff.abs().gte(params.change_threshold_db)
        vectors = (
            diff.updateMask(significant)
            .reduceToVectors(
                geometry=geom,
                scale=params.reduce_scale_m,
                geometryType="polygon",
                reducer=ee.Reducer.mean(),
                labelProperty="zone",
                maxPixels=1e9,
                bestEffort=True,
            )
            .map(lambda f: f.set("area_m2", f.geometry().area(maxError=1)))
            .filter(ee.Filter.gte("area_m2", params.min_area_m2))
        )

        fc = vectors.getInfo()
        patches: list[ChangePatch] = []
        for feat in fc.get("features", []):
            g = feat.get("geometry", {})
            props = feat.get("properties", {})
            mean_db = float(props.get("mean", props.get("change_db", 0.0)) or 0.0)
            area_m2 = float(props.get("area_m2", 0.0) or 0.0)
            patches.append(
                ChangePatch(
                    geometry=g,
                    centroid=_geometry_centroid(g),
                    mean_change_db=mean_db,
                    area_m2=area_m2,
                )
            )

        return ChangeResult(
            patches=patches,
            baseline_scene_count=base_n,
            recent_scene_count=rec_n,
            polarization=params.polarization,
            orbit_pass=params.orbit_pass,
        )
