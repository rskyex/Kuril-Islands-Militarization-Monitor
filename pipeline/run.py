"""Pipeline orchestrator.

Iterates the configured areas of interest, runs each enabled source's
``fetch`` + ``detect``, and upserts the resulting candidate events into the
store. Idempotent and re-runnable.

Usage:
    python -m pipeline.run                          # all AOIs, FIRMS, last 7 days
    python -m pipeline.run --days 3                 # shorter lookback window
    python -m pipeline.run --aoi matua-airfield
    python -m pipeline.run --dry-run                # fetch + detect, do not write
    python -m pipeline.run --source sentinel-1 --days 240   # SAR change detection

Sources are registered below. FIRMS runs by default (Phase 1). Sentinel-1 SAR
(Phase 2) is opt-in via ``--source`` because it needs Earth Engine credentials;
optical / AIS remain stubs until their phases land.
"""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import date, timedelta
from typing import Callable

from .config import AOI, load_aois
from .imagery_store import ImageryStore
from .models import Event
from .sources.base import Source
from .sources.firms import FirmsSource
from .sources.optical import OpticalSource
from .sources.sar import SarSource
from .store import EventStore

logger = logging.getLogger("pipeline.run")

# Registry of available sources. ``--source`` selects from these keys; FIRMS is
# the default. Each value is a factory so a source is only constructed (and its
# dependencies touched) when actually selected.
SOURCE_REGISTRY: dict[str, Callable[[], Source]] = {
    "firms": FirmsSource,
    "sentinel-1": SarSource,
}
DEFAULT_SOURCES = ["firms"]


def build_sources(names: list[str]) -> list[Source]:
    """Instantiate the selected sources, validating names."""
    sources: list[Source] = []
    for name in names:
        factory = SOURCE_REGISTRY.get(name)
        if factory is None:
            raise SystemExit(
                f"Unknown source '{name}'. Available: {', '.join(SOURCE_REGISTRY)}"
            )
        sources.append(factory())
    return sources


def run_source(source: Source, aoi: AOI, since: date) -> list[Event]:
    """Fetch + detect for one source over one AOI, logging failures softly."""
    try:
        raw = source.fetch(aoi, since)
    except Exception as exc:  # noqa: BLE001 — one failing source must not abort the run
        logger.warning("[%s] fetch failed for %s: %s", source.name, aoi.id, exc)
        return []

    events = source.detect(aoi, raw)
    logger.info(
        "[%s] %s: %d raw record(s) -> %d event(s)",
        source.name,
        aoi.id,
        len(raw),
        len(events),
    )
    return events


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Kuril monitor pipeline runner")
    parser.add_argument("--days", type=int, default=7, help="Lookback window in days (default 7)")
    parser.add_argument("--aoi", action="append", help="Limit to AOI id(s); repeatable")
    parser.add_argument(
        "--source",
        action="append",
        help=f"Source(s) to run (repeatable). Available: {', '.join(SOURCE_REGISTRY)}. Default: {', '.join(DEFAULT_SOURCES)}",
    )
    parser.add_argument(
        "--imagery",
        action="store_true",
        help="Collect Sentinel-2 clear-day imagery (Phase 3). Alone = imagery only; "
        "combine with --source to also run event sources. Needs Earth Engine.",
    )
    parser.add_argument("--dry-run", action="store_true", help="Do not write the store")
    parser.add_argument("--verbose", "-v", action="store_true", help="Debug logging")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
    )

    aois = load_aois()
    if args.aoi:
        wanted = set(args.aoi)
        aois = [a for a in aois if a.id in wanted]
        if not aois:
            logger.error("No matching AOIs for %s", sorted(wanted))
            return 2

    since = date.today() - timedelta(days=max(1, args.days))

    # `--imagery` alone runs imagery only; otherwise event sources run too.
    run_events = bool(args.source) or not args.imagery
    sources = build_sources(args.source or DEFAULT_SOURCES) if run_events else []
    logger.info(
        "Running %d event source(s)%s over %d AOI(s), since %s",
        len(sources),
        " + imagery" if args.imagery else "",
        len(aois),
        since.isoformat(),
    )

    all_events: list[Event] = []
    for aoi in aois:
        for source in sources:
            all_events.extend(run_source(source, aoi, since))

    if args.imagery:
        collect_imagery(aois, since, dry_run=args.dry_run)

    if args.dry_run:
        logger.info("Dry run: %d event(s) detected, not written.", len(all_events))
        return 0

    written = EventStore().upsert(all_events)
    logger.info("Wrote %d event(s) to the store.", written)
    return 0


def collect_imagery(aois: list[AOI], since: date, dry_run: bool) -> None:
    """Run the Sentinel-2 optical collection over each AOI, logging softly."""
    optical = OpticalSource()
    store = ImageryStore()
    for aoi in aois:
        try:
            collected = optical.collect(aoi, since)
        except Exception as exc:  # noqa: BLE001 — one AOI must not abort the run
            logger.warning("[sentinel-2] imagery failed for %s: %s", aoi.id, exc)
            continue
        if collected is None:
            logger.info("[sentinel-2] %s: no clear-day scene found", aoi.id)
            continue
        if dry_run:
            logger.info("[sentinel-2] %s: imagery collected (dry run, not saved)", aoi.id)
            continue
        store.save(collected)
        logger.info("[sentinel-2] %s: imagery saved", aoi.id)


if __name__ == "__main__":
    sys.exit(main())
