"""Abstract source interface shared by all data sources."""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date
from typing import Any

from ..config import AOI
from ..models import Event


class Source(ABC):
    """A free data source that can be fetched and turned into candidate events.

    Implementations should be idempotent and stamp provenance (source +
    retrieval time) onto every event they emit.
    """

    #: Short stable identifier, e.g. ``"firms"``.
    name: str = "base"

    @abstractmethod
    def fetch(self, aoi: AOI, since: date) -> list[dict[str, Any]]:
        """Pull raw observations for ``aoi`` no older than ``since``.

        Returns source-specific raw records (e.g. parsed CSV rows). Network
        and parsing live here; no detection logic.
        """

    @abstractmethod
    def detect(self, aoi: AOI, window: list[dict[str, Any]]) -> list[Event]:
        """Turn a window of raw observations into candidate :class:`Event`s.

        All emitted events must be ``status="unverified"`` and carry a
        ``source_url`` back to the underlying data.
        """
