"""Per-source ingestion + detection modules.

Each source module exposes a class implementing :class:`~pipeline.sources.base.Source`
with ``fetch(aoi, since)`` and ``detect(aoi, window)`` returning structured
candidate-event records.
"""
