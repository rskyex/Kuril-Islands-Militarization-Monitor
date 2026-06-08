"""Configuration loading: areas of interest and environment-based settings.

No secrets live in the repo. API keys are read from environment variables
only (see README). The AOI list is loaded from ``data/aois.geojson`` — the
single editable config for monitored sites.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

# Repository layout anchors. ``config.py`` lives in ``pipeline/``; the repo
# root is its parent, and the data store sits in ``data/`` at the root.
PIPELINE_DIR = Path(__file__).resolve().parent
REPO_ROOT = PIPELINE_DIR.parent
DATA_DIR = REPO_ROOT / "data"

AOIS_PATH = DATA_DIR / "aois.geojson"
EVENTS_PATH = DATA_DIR / "events.json"


@dataclass(frozen=True)
class BBox:
    """Geographic bounding box in EPSG:4326 (lon/lat)."""

    west: float
    south: float
    east: float
    north: float

    def as_firms_area(self) -> str:
        """Format as the FIRMS area API expects: ``west,south,east,north``."""
        return f"{self.west},{self.south},{self.east},{self.north}"


@dataclass(frozen=True)
class AOI:
    """A monitored area of interest, loaded from ``aois.geojson``."""

    id: str
    name: str
    name_ja: str
    island: str
    facility_type: str
    center: tuple[float, float]  # (lon, lat)
    geometry: dict[str, Any]  # GeoJSON Polygon geometry
    notes: str = ""

    @property
    def bbox(self) -> BBox:
        """Axis-aligned bounding box of the AOI polygon."""
        coords = _iter_coords(self.geometry)
        lons = [c[0] for c in coords]
        lats = [c[1] for c in coords]
        return BBox(min(lons), min(lats), max(lons), max(lats))


def _iter_coords(geometry: dict[str, Any]) -> list[tuple[float, float]]:
    """Flatten a Polygon/MultiPolygon geometry into a list of (lon, lat)."""
    gtype = geometry.get("type")
    coords = geometry.get("coordinates", [])
    out: list[tuple[float, float]] = []
    if gtype == "Polygon":
        for ring in coords:
            out.extend((float(p[0]), float(p[1])) for p in ring)
    elif gtype == "MultiPolygon":
        for poly in coords:
            for ring in poly:
                out.extend((float(p[0]), float(p[1])) for p in ring)
    elif gtype == "Point":
        out.append((float(coords[0]), float(coords[1])))
    else:
        raise ValueError(f"Unsupported AOI geometry type: {gtype!r}")
    return out


def load_aois(path: Path = AOIS_PATH) -> list[AOI]:
    """Load and validate areas of interest from the GeoJSON config."""
    with path.open("r", encoding="utf-8") as fh:
        fc = json.load(fh)

    if fc.get("type") != "FeatureCollection":
        raise ValueError(f"{path} is not a GeoJSON FeatureCollection")

    aois: list[AOI] = []
    seen: set[str] = set()
    for feature in fc.get("features", []):
        props = feature.get("properties", {})
        aoi_id = props.get("id")
        if not aoi_id:
            raise ValueError("AOI feature missing 'id' property")
        if aoi_id in seen:
            raise ValueError(f"Duplicate AOI id: {aoi_id}")
        seen.add(aoi_id)

        center = props.get("center")
        if not (isinstance(center, (list, tuple)) and len(center) == 2):
            raise ValueError(f"AOI {aoi_id} missing valid 'center' [lon, lat]")

        aois.append(
            AOI(
                id=aoi_id,
                name=props.get("name", aoi_id),
                name_ja=props.get("name_ja", props.get("name", aoi_id)),
                island=props.get("island", ""),
                facility_type=props.get("facility_type", "other"),
                center=(float(center[0]), float(center[1])),
                geometry=feature["geometry"],
                notes=props.get("notes", ""),
            )
        )

    if not aois:
        raise ValueError(f"No AOIs found in {path}")
    return aois


# --- Environment-based settings (no secrets committed) ---------------------


def firms_map_key() -> Optional[str]:
    """NASA FIRMS map key from the environment (``FIRMS_MAP_KEY``).

    Returns ``None`` if unset so callers can degrade gracefully / explain.
    """
    key = os.environ.get("FIRMS_MAP_KEY", "").strip()
    return key or None
