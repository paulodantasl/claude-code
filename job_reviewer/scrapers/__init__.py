"""Scraper registry — maps an agency's `type` to its scraper class."""
from __future__ import annotations

from typing import Any

from .base import BaseJobScraper, RawJob
from .governmentjobs import GovernmentJobsScraper

SCRAPERS: dict[str, type[BaseJobScraper]] = {
    "governmentjobs": GovernmentJobsScraper,
    "neogov": GovernmentJobsScraper,
}


def get_scraper(agency_config: dict[str, Any]) -> BaseJobScraper:
    """Return the scraper instance for an agency config dict."""
    portal_type = agency_config.get("type", "governmentjobs")
    cls = SCRAPERS.get(portal_type)
    if cls is None:
        raise ValueError(
            f"Unknown portal type '{portal_type}' for agency "
            f"'{agency_config.get('id')}'. Known: {sorted(SCRAPERS)}"
        )
    return cls(agency_config)


__all__ = ["BaseJobScraper", "RawJob", "GovernmentJobsScraper", "get_scraper"]
