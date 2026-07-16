"""
County Property Appraiser enrichment for the owner.

Fills the owner's **mailing address** (and normalises the owner name) by looking
up the permit's parcel in the county property appraiser — reusing the package's
existing appraiser scrapers:

  hillsborough_county → HillsboroughPropertyScraper (public ArcGIS, no browser)
  pasco_county        → PascoPropertyScraper       (Playwright web scraper)

Counties without a supported appraiser scraper are skipped. The lookup is
injectable (``lookup_fn``) so the whole path is testable with no network, and so
you can point it at your own data source.
"""
from __future__ import annotations

import logging
from typing import Any, Callable

from .base import Enricher, EnrichmentResult

logger = logging.getLogger(__name__)

# Counties with a supported appraiser scraper.
SUPPORTED_COUNTIES = {"hillsborough_county", "pasco_county"}


def _default_lookup(county_id: str, parcel: str | None, owner_name: str | None) -> Any | None:
    """Real appraiser lookup. Imported lazily to avoid pulling heavy deps."""
    try:
        from ...scrapers.property_appraiser import (
            HillsboroughPropertyScraper,
            PascoPropertyScraper,
        )
    except Exception as exc:  # tenacity/playwright may be absent
        logger.warning("Property appraiser scrapers unavailable: %s", exc)
        return None

    if county_id == "hillsborough_county":
        s = HillsboroughPropertyScraper()
        if parcel:
            prop = s.lookup_by_parcel(parcel)
            if prop:
                return prop
        if owner_name:
            props = s.scrape_by_owner([owner_name])
            return props[0] if props else None
    elif county_id == "pasco_county":
        s = PascoPropertyScraper()
        if parcel:
            return s.lookup_by_parcel(parcel)
    return None


class PropertyAppraiserEnricher(Enricher):
    """Enrich the owner's mailing address from the county property appraiser."""

    name = "property_appraiser"

    def __init__(
        self,
        counties: list[str] | None = None,
        lookup_fn: Callable[[str, str | None, str | None], Any] | None = None,
    ):
        # Which counties to attempt (default: all supported).
        self.counties = set(counties) if counties else set(SUPPORTED_COUNTIES)
        self._lookup = lookup_fn or _default_lookup

    def cache_key(self, lead) -> str | None:
        if lead.county_id not in self.counties:
            return None
        ident = lead.parcel_number or lead.owner_name
        if not ident:
            return None
        return f"{lead.county_id}:{ident}"

    def enrich(self, lead) -> EnrichmentResult:
        # Nothing to gain if we already have the owner's mailing address.
        if lead.owner_mailing_address:
            return EnrichmentResult(source=self.name)
        if lead.county_id not in self.counties:
            return EnrichmentResult(source=self.name)
        if not (lead.parcel_number or lead.owner_name):
            return EnrichmentResult(source=self.name)

        try:
            prop = self._lookup(lead.county_id, lead.parcel_number, lead.owner_name)
        except Exception as exc:
            logger.info("Appraiser lookup failed for %s: %s", lead.parcel_number, exc)
            return EnrichmentResult(source=self.name)

        if not prop:
            return EnrichmentResult(source=self.name)

        mailing = getattr(prop, "mailing_address", None)
        return EnrichmentResult(
            owner_mailing_address=mailing or None,
            source=self.name,
        )
