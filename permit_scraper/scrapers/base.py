"""Abstract base class for all permit scrapers."""
from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)


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
