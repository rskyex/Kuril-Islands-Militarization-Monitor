"""Satellite-relayed AIS naval-activity source — PHASE 4 (stretch).

Surfaces vessel activity in the bays adjacent to the bases as ``naval``
candidate events, using a free real-time AIS feed (AISStream.io). AIS is a
live WebSocket stream (no historical query), so this source *listens* over each
AOI's bounding box for a short window, then aggregates the position reports it
saw per vessel (MMSI) into one unverified naval candidate event each.

Same testability contract as the SAR / optical sources: all streaming I/O is
behind :class:`AisBackend` (a ``Protocol``); the real
:class:`AisStreamBackend` lazily imports ``websockets`` so this module imports
without it and the aggregation logic is unit-tested with a fake backend.

Running it for real (locally):

    pip install -r pipeline/requirements.txt -r pipeline/requirements-ais.txt
    export AISSTREAM_API_KEY=...      # free key from https://aisstream.io/
    python -m pipeline.run --source ais

Note: AIS traffic is mostly civilian; every event is an unverified candidate,
and the ship type is recorded so analysts can filter. The verification link
points to a public vessel-tracking page by MMSI.
"""

from __future__ import annotations

import os
from collections import defaultdict
from datetime import date, datetime, timezone
from typing import Any, Optional, Protocol

from ..config import AOI
from ..models import Event, Provenance, utc_now_iso
from .base import Source

# Normalization reference for signal_strength: a vessel seen this many times in
# the listening window is treated as a strong/persistent presence (documented,
# tunable — not a calibrated threshold).
REPORT_COUNT_REFERENCE = 20.0
# Speed (knots) above which a vessel is likely transiting rather than loitering.
TRANSIT_SPEED_KNOTS = 12.0


class AisBackend(Protocol):
    """Pluggable backend that listens for AIS position reports over a bbox."""

    def collect_positions(
        self, west: float, south: float, east: float, north: float, listen_seconds: int
    ) -> list[dict[str, Any]]: ...


class AisSource(Source):
    """AIS naval-activity source."""

    name = "ais"

    def __init__(self, backend: Optional[AisBackend] = None, listen_seconds: int = 60) -> None:
        self._backend = backend
        self.listen_seconds = listen_seconds

    @property
    def backend(self) -> AisBackend:
        if self._backend is None:
            self._backend = AisStreamBackend()
        return self._backend

    # -- fetch --------------------------------------------------------------

    def fetch(self, aoi: AOI, since: date) -> list[dict[str, Any]]:
        """Listen over the AOI bbox and return raw position reports.

        ``since`` is unused: AIS is a live stream with no historical query.
        """
        b = aoi.bbox
        return self.backend.collect_positions(
            b.west, b.south, b.east, b.north, self.listen_seconds
        )

    # -- detect -------------------------------------------------------------

    def detect(self, aoi: AOI, window: list[dict[str, Any]]) -> list[Event]:
        """Aggregate position reports per vessel (MMSI) into naval events."""
        by_mmsi: dict[int, list[dict[str, Any]]] = defaultdict(list)
        for row in window:
            mmsi = row.get("mmsi")
            if mmsi is not None:
                by_mmsi[int(mmsi)].append(row)

        retrieved_at = utc_now_iso()
        events: list[Event] = []
        for mmsi, reports in by_mmsi.items():
            events.append(self._build_event(aoi, mmsi, reports, retrieved_at))
        return events

    def _build_event(
        self, aoi: AOI, mmsi: int, reports: list[dict[str, Any]], retrieved_at: str
    ) -> Event:
        latest = max(reports, key=lambda r: str(r.get("timestamp", "")))
        lon = float(latest.get("lon", aoi.center[0]))
        lat = float(latest.get("lat", aoi.center[1]))
        ts = str(latest.get("timestamp", "")) or f"{date.today().isoformat()}T00:00:00Z"
        day = ts[:10]

        name = str(latest.get("name", "") or "").strip() or "不明"
        ship_type = str(latest.get("ship_type", "") or "").strip() or "不明"
        sog = float(latest.get("sog", 0.0) or 0.0)

        # Persistent + slow (loitering / anchored) presence scores higher than a
        # single fast transit. Heuristic prioritization, not a verdict.
        persistence = min(1.0, len(reports) / REPORT_COUNT_REFERENCE)
        loiter = 1.0 - min(1.0, sog / TRANSIT_SPEED_KNOTS)
        signal_strength = round(min(1.0, 0.6 * persistence + 0.4 * loiter), 3)

        notes = (
            f"AIS 艦船・船舶を検出（{aoi.name_ja}周辺）。"
            f"MMSI {mmsi}、船名「{name}」、船種 {ship_type}、"
            f"観測 {len(reports)} 回、最新速力 {sog:.1f} ノット。"
            "民間船を含む未確認の候補です。船舶追跡サービスで確認してください。"
        )

        provenance = Provenance(
            source=self.name,
            dataset="AISStream.io PositionReport",
            retrieved_at=retrieved_at,
            query=f"bbox={aoi.bbox.as_firms_area()} listen_s={self.listen_seconds}",
        )

        return Event(
            id=f"ais-{aoi.id}-{mmsi}-{day}",
            aoi_id=aoi.id,
            date=day,
            type="naval",
            signal_strength=signal_strength,
            status="unverified",
            source_url=f"https://www.marinetraffic.com/en/ais/details/ships/mmsi:{mmsi}",
            geometry={"type": "Point", "coordinates": [lon, lat]},
            notes=notes,
            provenance=provenance,
            raw={
                "mmsi": mmsi,
                "name": name,
                "ship_type": ship_type,
                "report_count": len(reports),
                "latest_sog_knots": sog,
                "track": [
                    [float(r.get("lon", lon)), float(r.get("lat", lat))]
                    for r in sorted(reports, key=lambda r: str(r.get("timestamp", "")))
                ],
            },
        )


# --------------------------------------------------------------------------
# Real AISStream.io backend (lazy-imports websockets)
# --------------------------------------------------------------------------


class AisStreamBackend:
    """Connects to AISStream.io and collects position reports over a window."""

    STREAM_URL = "wss://stream.aisstream.io/v0/stream"

    def __init__(self, api_key: Optional[str] = None) -> None:
        self.api_key = api_key or os.environ.get("AISSTREAM_API_KEY") or None

    def collect_positions(
        self, west: float, south: float, east: float, north: float, listen_seconds: int
    ) -> list[dict[str, Any]]:  # pragma: no cover - requires network + key
        if not self.api_key:
            raise RuntimeError(
                "AISSTREAM_API_KEY is not set. Get a free key at "
                "https://aisstream.io/ and export it as AISSTREAM_API_KEY."
            )
        import asyncio

        return asyncio.run(self._stream(west, south, east, north, listen_seconds))

    async def _stream(
        self, west: float, south: float, east: float, north: float, listen_seconds: int
    ) -> list[dict[str, Any]]:  # pragma: no cover - requires network + key
        import asyncio
        import json

        try:
            import websockets  # type: ignore
        except ImportError as exc:
            raise RuntimeError(
                "websockets is not installed. Install it with "
                "`pip install -r pipeline/requirements-ais.txt` to run the AIS source."
            ) from exc

        loop = asyncio.get_event_loop()
        deadline = loop.time() + listen_seconds
        statics: dict[int, dict[str, Any]] = {}
        reports: list[dict[str, Any]] = []

        subscribe = {
            "APIKey": self.api_key,
            # AISStream bbox: [[[lat, lon] (SW), [lat, lon] (NE)]]
            "BoundingBoxes": [[[south, west], [north, east]]],
            "FilterMessageTypes": ["PositionReport", "ShipStaticData"],
        }

        async with websockets.connect(self.STREAM_URL) as ws:
            await ws.send(json.dumps(subscribe))

            while loop.time() < deadline:
                try:
                    raw = await asyncio.wait_for(
                        ws.recv(), timeout=max(1.0, deadline - loop.time())
                    )
                except asyncio.TimeoutError:
                    break
                msg = json.loads(raw)
                meta = msg.get("MetaData", {})
                mmsi = meta.get("MMSI")
                mtype = msg.get("MessageType")
                body = msg.get("Message", {})
                if mtype == "ShipStaticData" and mmsi is not None:
                    sd = body.get("ShipStaticData", {})
                    statics[int(mmsi)] = {
                        "name": (sd.get("Name") or meta.get("ShipName") or "").strip(),
                        "ship_type": sd.get("Type"),
                    }
                elif mtype == "PositionReport" and mmsi is not None:
                    pr = body.get("PositionReport", {})
                    reports.append(
                        {
                            "mmsi": int(mmsi),
                            "lat": pr.get("Latitude"),
                            "lon": pr.get("Longitude"),
                            "sog": pr.get("Sog"),
                            "cog": pr.get("Cog"),
                            "timestamp": meta.get("time_utc")
                            or datetime.now(timezone.utc).isoformat(),
                        }
                    )

        # Merge static (name / type) into each report.
        for r in reports:
            sd = statics.get(r["mmsi"])
            if sd:
                r.setdefault("name", sd.get("name"))
                r.setdefault("ship_type", sd.get("ship_type"))
        return reports
