"""Abstract base class for all permit scrapers."""
from __future__ import annotations

import logging
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)


def _norm_num(value: str | None) -> str:
    """Normalise a permit/record number for matching (upper, strip separators)."""
    if not value:
        return ""
    return re.sub(r"[\s\-_/.]", "", str(value)).upper()


def _norm_addr(value: str | None) -> str:
    """Normalise an address for loose matching (collapse whitespace, upper)."""
    if not value:
        return ""
    return re.sub(r"\s+", " ", str(value)).strip().upper()


@dataclass
class RawPermit:
    """Normalised permit data before DB insert."""

    source_id: str
    county_id: str
    county_name: str
    permit_number: str | None = None
    permit_type: str | None = None
    permit_subtype: str | None = None
    status: str | None = None
    description: str | None = None
    applicant_name: str | None = None
    owner_name: str | None = None
    contractor_name: str | None = None
    address: str | None = None
    city: str | None = None
    state: str | None = None
    zip_code: str | None = None
    parcel_number: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    estimated_value: float | None = None
    total_sqft: float | None = None
    filed_date: datetime | None = None
    issued_date: datetime | None = None
    expiry_date: datetime | None = None
    source_url: str | None = None
    raw_data: dict[str, Any] = field(default_factory=dict)


class BaseScraper(ABC):
    """All scrapers implement this interface."""

    def __init__(self, county_config: dict[str, Any]):
        self.config = county_config
        self.county_id: str = county_config["id"]
        self.county_name: str = county_config["name"]
        self.logger = logging.getLogger(f"{__name__}.{self.county_id}")

    @abstractmethod
    def scrape(
        self,
        days_back: int = 7,
        permit_types: list[str] | None = None,
    ) -> list[RawPermit]:
        """
        Fetch recent permits.

        Args:
            days_back: How many calendar days to look back.
            permit_types: Optional list of permit type keywords to filter by.

        Returns:
            List of normalised RawPermit objects.
        """
        ...

    # ── Per-permit lookup (used by the monitoring feature) ───────────────────

    def fetch_permits(
        self,
        refs: list[Any],
        lookback_days: int = 180,
    ) -> dict[str, RawPermit | None]:
        """
        Return the current state of a batch of specific permits.

        ``refs`` is any list of objects exposing ``.permit_number`` and
        (optionally) ``.address``. Returns ``{permit_number: RawPermit | None}``;
        ``None`` means the permit was not found this run.

        The default implementation performs ONE bulk scrape over the lookback
        window and indexes the results by permit number and address — so N
        tracked permits in a county cost a single scrape. Scrapers that expose a
        direct record lookup (e.g. :class:`AccelaApiScraper`) override this both
        for efficiency and to reach permits older than the lookback window.
        """
        results: dict[str, RawPermit | None] = {
            getattr(r, "permit_number", None): None for r in refs
        }
        try:
            raws = self.scrape(days_back=lookback_days)
        except Exception as exc:
            self.logger.error("fetch_permits bulk scrape failed for %s: %s", self.county_name, exc)
            return results

        by_num: dict[str, RawPermit] = {}
        by_addr: dict[str, RawPermit] = {}
        for raw in raws:
            if raw.permit_number:
                by_num.setdefault(_norm_num(raw.permit_number), raw)
            if raw.address:
                by_addr.setdefault(_norm_addr(raw.address), raw)

        for ref in refs:
            pnum = getattr(ref, "permit_number", None)
            addr = getattr(ref, "address", None)
            match = by_num.get(_norm_num(pnum)) if pnum else None
            if match is None and addr:
                match = by_addr.get(_norm_addr(addr))
            results[pnum] = match
        return results

    def fetch_permit(
        self,
        permit_number: str,
        address: str | None = None,
        lookback_days: int = 180,
    ) -> RawPermit | None:
        """Convenience single-permit wrapper around :meth:`fetch_permits`."""
        ref = type("_Ref", (), {"permit_number": permit_number, "address": address})()
        return self.fetch_permits([ref], lookback_days=lookback_days).get(permit_number)

    def _parse_date(self, value: Any) -> datetime | None:
        if not value:
            return None
        if isinstance(value, datetime):
            return value
        for fmt in ("%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d", "%m/%d/%Y"):
            try:
                return datetime.strptime(str(value).strip(), fmt)
            except ValueError:
                continue
        return None

    def _parse_float(self, value: Any) -> float | None:
        if value is None:
            return None
        try:
            return float(str(value).replace(",", "").replace("$", "").strip())
        except (ValueError, TypeError):
            return None
