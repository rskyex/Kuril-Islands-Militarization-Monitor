"""Sentinel-1 (C-band SAR) source — PHASE 2 (not yet implemented).

Primary sensor for the monitor: SAR sees through cloud and polar night, which
matters at Kuril latitudes. Planned approach (see project plan):

- Ingest Sentinel-1 GRD scenes over each AOI via Google Earth Engine
  (``earthengine-api``) or the Copernicus Data Space Ecosystem.
- Backscatter change detection: compare a recent window against a baseline and
  flag pixels/areas with significant change.
- Where feasible, use interferometric coherence loss to flag new construction,
  cleared ground, and large equipment movement.
- Emit unverified ``construction`` / ``clearance`` candidate events, each
  linked to the underlying scene.

This stub keeps the orchestrator wiring honest: ``fetch``/``detect`` exist and
return nothing until Phase 2.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from ..config import AOI
from ..models import Event
from .base import Source


class SarSource(Source):
    """Placeholder Sentinel-1 source. Implemented in Phase 2."""

    name = "sentinel-1"

    def fetch(self, aoi: AOI, since: date) -> list[dict[str, Any]]:  # noqa: ARG002
        raise NotImplementedError("Sentinel-1 SAR ingestion is a Phase 2 task.")

    def detect(self, aoi: AOI, window: list[dict[str, Any]]) -> list[Event]:  # noqa: ARG002
        raise NotImplementedError("SAR change detection is a Phase 2 task.")
