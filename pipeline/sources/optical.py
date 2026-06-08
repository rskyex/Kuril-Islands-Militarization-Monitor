"""Sentinel-2 (optical, 10 m) clear-day imagery — PHASE 3.

Secondary sensor, used on the rare clear days for *visual confirmation* of
SAR-flagged change. Unlike FIRMS / Sentinel-1, this source does not emit
detection events: it provides per-AOI true-color imagery context — a baseline
scene and a recent scene — for an analyst to compare beside the SAR signal in
the detail panel. Nothing here is a detection; it is reference imagery a human
uses to verify candidates.

Same testability contract as the SAR source: all Earth Engine access is behind
:class:`OpticalBackend` (a ``Protocol``); :class:`EeBackend` lazily imports
``earthengine-api`` (and ``requests``) so this module imports without them and
the collection logic is unit-tested with a fake backend.

Running it for real (locally), after `earthengine authenticate` + `EE_PROJECT`:

    pip install -r pipeline/requirements.txt -r pipeline/requirements-ee.txt
    python -m pipeline.run --imagery --days 540

Imagery is written under ``data/imagery/<aoi>/{baseline,recent}.png`` and
indexed in ``data/imagery.json``; the web app serves it via an API route.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Any, Optional, Protocol

from ..config import AOI
from ..models import Provenance, utc_now_iso

S2_COLLECTION = "COPERNICUS/S2_SR_HARMONIZED"


@dataclass(frozen=True)
class OpticalParams:
    """Tunable parameters for Sentinel-2 clear-day selection + thumbnails."""

    max_cloud_pct: float = 40.0      # Skip scenes cloudier than this.
    thumb_dimensions: int = 512      # Thumbnail max edge in pixels.
    vis_min: float = 0.0             # True-color stretch min (reflectance * 1e4).
    vis_max: float = 3000.0          # True-color stretch max.


@dataclass(frozen=True)
class SceneRef:
    """A selected Sentinel-2 scene."""

    scene_id: str
    date: str           # ISO date (YYYY-MM-DD)
    cloud_pct: Optional[float]


@dataclass(frozen=True)
class ImageRef:
    """A rendered thumbnail reference for the frontend."""

    date: str
    cloud_pct: Optional[float]
    image_url: str       # URL the web app loads (served via API route)
    scene_id: Optional[str]
    source_url: str      # Deep link to the scene in the EO Browser


@dataclass(frozen=True)
class AoiImagery:
    """Baseline + recent imagery context for one AOI."""

    aoi_id: str
    baseline: Optional[ImageRef]
    recent: Optional[ImageRef]
    provenance: Optional[Provenance] = None

    def to_dict(self) -> dict[str, Any]:
        def ref(r: Optional[ImageRef]) -> Optional[dict[str, Any]]:
            return None if r is None else r.__dict__.copy()

        return {
            "aoi_id": self.aoi_id,
            "baseline": ref(self.baseline),
            "recent": ref(self.recent),
            "provenance": self.provenance.to_dict() if self.provenance else None,
        }


@dataclass(frozen=True)
class CollectedImagery:
    """Result of collecting imagery for one AOI: the index record + the bytes.

    Separating the record (paths/metadata) from the bytes keeps
    :meth:`OpticalSource.collect` free of filesystem side effects, so it is
    unit-testable; :class:`~pipeline.imagery_store.ImageryStore` persists both.
    """

    imagery: AoiImagery
    files: dict[str, bytes]   # relative path under the imagery dir -> PNG bytes


class OpticalBackend(Protocol):
    """Pluggable backend for Sentinel-2 scene selection + thumbnail rendering."""

    def best_scene(
        self, aoi_geometry: dict[str, Any], start: str, end: str, params: OpticalParams
    ) -> Optional[SceneRef]: ...

    def thumbnail_png(
        self, scene_id: str, aoi_geometry: dict[str, Any], params: OpticalParams
    ) -> bytes: ...


# --------------------------------------------------------------------------
# Source
# --------------------------------------------------------------------------


class OpticalSource:
    """Sentinel-2 clear-day imagery provider (baseline vs recent)."""

    name = "sentinel-2"

    def __init__(
        self,
        backend: Optional[OpticalBackend] = None,
        params: OpticalParams = OpticalParams(),
        recent_days: int = 60,
        baseline_days: int = 540,
    ) -> None:
        # Optical needs the rare clear day, so the windows are wide.
        self._backend = backend
        self.params = params
        self.recent_days = recent_days
        self.baseline_days = baseline_days

    @property
    def backend(self) -> OpticalBackend:
        if self._backend is None:
            self._backend = EeBackend()
        return self._backend

    def windows(self, since: date, today: Optional[date] = None) -> tuple[str, str, str, str]:
        """(baseline_start, baseline_end, recent_start, recent_end) ISO dates."""
        today = today or date.today()
        recent_start = today - timedelta(days=self.recent_days)
        baseline_end = recent_start
        baseline_start = max(since, baseline_end - timedelta(days=self.baseline_days))
        return (
            baseline_start.isoformat(),
            baseline_end.isoformat(),
            recent_start.isoformat(),
            today.isoformat(),
        )

    def collect(self, aoi: AOI, since: date) -> Optional[CollectedImagery]:
        """Select clear baseline + recent scenes and render their thumbnails."""
        b_start, b_end, r_start, r_end = self.windows(since)

        baseline_scene = self.backend.best_scene(aoi.geometry, b_start, b_end, self.params)
        recent_scene = self.backend.best_scene(aoi.geometry, r_start, r_end, self.params)
        if baseline_scene is None and recent_scene is None:
            return None

        files: dict[str, bytes] = {}
        baseline_ref = self._render(aoi, baseline_scene, "baseline", files)
        recent_ref = self._render(aoi, recent_scene, "recent", files)

        imagery = AoiImagery(
            aoi_id=aoi.id,
            baseline=baseline_ref,
            recent=recent_ref,
            provenance=Provenance(
                source=self.name,
                dataset=S2_COLLECTION,
                retrieved_at=utc_now_iso(),
                query=f"baseline={b_start}..{b_end} recent={r_start}..{r_end}",
            ),
        )
        return CollectedImagery(imagery=imagery, files=files)

    def _render(
        self,
        aoi: AOI,
        scene: Optional[SceneRef],
        slot: str,
        files: dict[str, bytes],
    ) -> Optional[ImageRef]:
        if scene is None:
            return None
        png = self.backend.thumbnail_png(scene.scene_id, aoi.geometry, self.params)
        rel_path = f"{aoi.id}/{slot}.png"
        files[rel_path] = png
        lon, lat = aoi.center
        return ImageRef(
            date=scene.date,
            cloud_pct=scene.cloud_pct,
            image_url=f"/api/imagery/{rel_path}",
            scene_id=scene.scene_id,
            source_url=_eo_browser_s2_url(lon, lat, scene.date),
        )


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------


def _eo_browser_s2_url(lon: float, lat: float, day: str) -> str:
    """Deep link into the Copernicus EO Browser at the Sentinel-2 L2A scene."""
    return (
        "https://browser.dataspace.copernicus.eu/?"
        f"zoom=13&lat={lat:.4f}&lng={lon:.4f}"
        f"&fromTime={day}T00%3A00%3A00.000Z"
        f"&toTime={day}T23%3A59%3A59.999Z"
        "&datasetId=S2_L2A_CDAS"
    )


# --------------------------------------------------------------------------
# Real Earth Engine backend (lazy-imports earthengine-api + requests)
# --------------------------------------------------------------------------


class EeBackend:
    """Earth Engine implementation of :class:`OpticalBackend`."""

    def __init__(self, project: Optional[str] = None) -> None:
        self.project = project or os.environ.get("EE_PROJECT") or None
        self._initialized = False

    def _ee(self):
        try:
            import ee  # type: ignore
        except ImportError as exc:  # pragma: no cover - optional dependency
            raise RuntimeError(
                "earthengine-api is not installed. Install it with "
                "`pip install -r pipeline/requirements-ee.txt` to run the "
                "Sentinel-2 optical source."
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

    def best_scene(
        self, aoi_geometry: dict[str, Any], start: str, end: str, params: OpticalParams
    ) -> Optional[SceneRef]:  # pragma: no cover - requires EE credentials
        ee = self._ee()
        geom = ee.Geometry(aoi_geometry)
        col = (
            ee.ImageCollection(S2_COLLECTION)
            .filterBounds(geom)
            .filterDate(start, end)
            .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", params.max_cloud_pct))
            .sort("CLOUDY_PIXEL_PERCENTAGE")
        )
        if int(col.size().getInfo()) == 0:
            return None
        info = col.first().getInfo()
        props = info.get("properties", {})
        ts = props.get("system:time_start")
        day = (
            datetime.fromtimestamp(ts / 1000.0, tz=timezone.utc).date().isoformat()
            if ts
            else start
        )
        return SceneRef(
            scene_id=info.get("id", ""),
            date=day,
            cloud_pct=props.get("CLOUDY_PIXEL_PERCENTAGE"),
        )

    def thumbnail_png(
        self, scene_id: str, aoi_geometry: dict[str, Any], params: OpticalParams
    ) -> bytes:  # pragma: no cover - requires EE credentials
        ee = self._ee()
        import requests

        geom = ee.Geometry(aoi_geometry)
        img = ee.Image(scene_id).select(["B4", "B3", "B2"])
        url = img.getThumbURL(
            {
                "region": geom,
                "dimensions": params.thumb_dimensions,
                "min": params.vis_min,
                "max": params.vis_max,
                "format": "png",
            }
        )
        resp = requests.get(url, timeout=120)
        resp.raise_for_status()
        return resp.content
