"""Core data models shared across the pipeline.

The :class:`Event` shape is the contract between the Python pipeline and the
TypeScript frontend (see ``web/src/lib/types.ts``). Keep the two in sync.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal, Optional

# An event "type" describes what kind of candidate signal was detected.
EventType = Literal["construction", "thermal", "clearance", "naval", "other"]

# Events are always candidates surfaced from public data. They are never
# presented as confirmed military activity, hence the single allowed status.
EventStatus = Literal["unverified"]

# A GeoJSON geometry (Point / Polygon / etc.) as a plain dict.
Geometry = dict[str, Any]


@dataclass(frozen=True)
class Provenance:
    """Where an event came from and when it was retrieved.

    Recorded on every event so results are reproducible and auditable.
    """

    source: str
    """Short source identifier, e.g. ``"firms"``, ``"sentinel-1"``."""

    dataset: str
    """Specific dataset/product, e.g. ``"VIIRS_SNPP_NRT"``."""

    retrieved_at: str
    """ISO-8601 UTC timestamp of when the data was fetched."""

    query: Optional[str] = None
    """Human-readable description of the query used (no secrets)."""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class Event:
    """A single candidate event for one area of interest.

    Matches the TypeScript ``MonitorEvent`` type consumed by the web app.
    """

    id: str
    aoi_id: str
    date: str  # ISO-8601 (date or datetime) of the observed signal.
    type: EventType
    signal_strength: float  # Normalized 0..1 confidence/intensity proxy.
    source_url: str
    geometry: Geometry
    status: EventStatus = "unverified"
    notes: str = ""
    provenance: Optional[Provenance] = None
    raw: dict[str, Any] = field(default_factory=dict)
    """Source-specific raw fields, kept for traceability (not rendered)."""

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        # asdict already recursed into the Provenance dataclass.
        return d

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, sort_keys=True)


def utc_now_iso() -> str:
    """Current UTC time as an ISO-8601 string with a trailing ``Z``."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
