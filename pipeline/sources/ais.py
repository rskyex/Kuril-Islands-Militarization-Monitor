"""Satellite-relayed AIS naval-activity source — PHASE 4 stretch (not implemented).

Planned approach: subscribe to a free AIS feed (e.g. AISStream.io) and surface
vessel activity in the bays adjacent to the bases as ``naval`` candidate
events. This stub keeps the orchestrator wiring honest until Phase 4.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from ..config import AOI
from ..models import Event
from .base import Source


class AisSource(Source):
    """Placeholder AIS source. Implemented in Phase 4 (stretch)."""

    name = "ais"

    def fetch(self, aoi: AOI, since: date) -> list[dict[str, Any]]:  # noqa: ARG002
        raise NotImplementedError("AIS ingestion is a Phase 4 stretch task.")

    def detect(self, aoi: AOI, window: list[dict[str, Any]]) -> list[Event]:  # noqa: ARG002
        raise NotImplementedError("AIS detection is a Phase 4 stretch task.")
