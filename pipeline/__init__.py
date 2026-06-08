"""Kuril Islands Militarization Monitor — data pipeline.

Free-data OSINT pipeline that ingests public satellite / sensor data over a
set of areas of interest (AOIs), runs change/anomaly detection, and writes
structured *candidate* event records for the web frontend to display.

Design principles (see README):
- Free data sources only for the continuous monitoring layer.
- Every event is a candidate, labeled ``status="unverified"``, and carries a
  ``source_url`` linking back to the raw data so a human can confirm it.
- The pipeline is idempotent and re-runnable; provenance (source + retrieval
  time) is recorded on every event.
"""

__version__ = "0.1.0"
