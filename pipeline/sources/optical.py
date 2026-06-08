"""Sentinel-2 (optical, 10 m) source — PHASE 3 (not yet implemented).

Secondary sensor, used on the rare clear days for visual confirmation of
SAR-flagged changes. Planned approach:

- Retrieve Sentinel-2 L2A scenes over each AOI via the Copernicus Data Space
  Ecosystem or Google Earth Engine, filtered to low cloud cover.
- Provide baseline-vs-recent imagery shown beside the SAR signal in the
  per-facility detail panel.

This stub keeps the orchestrator wiring honest until Phase 3.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from ..config import AOI
from ..models import Event
from .base import Source


class OpticalSource(Source):
    """Placeholder Sentinel-2 source. Implemented in Phase 3."""

    name = "sentinel-2"

    def fetch(self, aoi: AOI, since: date) -> list[dict[str, Any]]:  # noqa: ARG002
        raise NotImplementedError("Sentinel-2 optical retrieval is a Phase 3 task.")

    def detect(self, aoi: AOI, window: list[dict[str, Any]]) -> list[Event]:  # noqa: ARG002
        raise NotImplementedError("Optical confirmation is a Phase 3 task.")
