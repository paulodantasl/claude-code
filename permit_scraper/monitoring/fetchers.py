"""
Fetchers supply the *current* state of a set of tracked permits in one county.

Two implementations ship:

  DictFetcher    — canned results keyed by permit number; used by tests, the
                   demo, and for feeding data from an external system.
  ScraperFetcher — wraps the county's real portal scraper (Accela, Socrata,
                   ArcGIS, …). Imported lazily so the monitoring core stays free
                   of the browser/DB dependencies.

A fetcher returns ``{permit_number: RawPermit | None}``; ``None`` means the
permit could not be found this run (portal down, record purged, wrong number) —
the monitor treats that as "no update" and leaves the last snapshot intact.
"""
from __future__ import annotations

import logging
from typing import Any, Protocol

logger = logging.getLogger(__name__)


class PermitRef:
    """Lightweight reference passed to scrapers (avoids a scraper→monitoring dep)."""

    __slots__ = ("permit_number", "address")

    def __init__(self, permit_number: str, address: str | None = None):
        self.permit_number = permit_number
        self.address = address


class Fetcher(Protocol):
    def fetch(self, county_config: dict[str, Any], refs: list[PermitRef]) -> dict[str, Any]:
        ...


class DictFetcher:
    """Return pre-supplied current states. Great for tests / external feeds.

    ``data`` maps ``permit_number`` → RawPermit-like object (or None).
    """

    def __init__(self, data: dict[str, Any]):
        self._data = data

    def fetch(self, county_config: dict[str, Any], refs: list[PermitRef]) -> dict[str, Any]:
        return {ref.permit_number: self._data.get(ref.permit_number) for ref in refs}


class ScraperFetcher:
    """Fetch live permit state from the county's configured portal scraper."""

    def __init__(self, lookback_days: int = 180):
        self.lookback_days = lookback_days

    def fetch(self, county_config: dict[str, Any], refs: list[PermitRef]) -> dict[str, Any]:
        # Lazy import: keeps playwright/requests-heavy scrapers out of the core.
        from ..scrapers import get_scraper

        scraper = get_scraper(county_config)
        try:
            return scraper.fetch_permits(refs, lookback_days=self.lookback_days)
        except Exception as exc:
            logger.error(
                "ScraperFetcher failed for county %s: %s",
                county_config.get("id"), exc,
            )
            return {ref.permit_number: None for ref in refs}
