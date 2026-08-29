"""Abstract base class for all job-posting scrapers."""
from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class RawJob:
    """Normalised job posting before DB insert."""

    source_id: str                       # stable ID from the source system
    agency_id: str                       # e.g. "pinellas_county"
    agency_name: str                     # e.g. "Pinellas County, FL"

    title: str | None = None
    department: str | None = None
    category: str | None = None
    job_type: str | None = None          # Full-Time, Part-Time, etc.
    location: str | None = None
    county: str | None = None            # pasco | hillsborough | pinellas
    salary_min: float | None = None
    salary_max: float | None = None
    salary_raw: str | None = None
    description: str | None = None        # full posting text (duties, etc.)
    requirements: str | None = None       # minimum qualifications section
    posted_date: datetime | None = None
    closing_date: datetime | None = None
    job_id_external: str | None = None    # the agency's own posting number
    apply_url: str | None = None          # direct apply / posting URL
    source_url: str | None = None
    raw_data: dict[str, Any] = field(default_factory=dict)

    @property
    def full_text(self) -> str:
        """Concatenated text used for matching against the candidate profile."""
        parts = [
            self.title,
            self.department,
            self.category,
            self.description,
            self.requirements,
        ]
        return "\n".join(p for p in parts if p)


class BaseJobScraper(ABC):
    """All job scrapers implement this interface."""

    def __init__(self, agency_config: dict[str, Any]):
        self.config = agency_config
        self.agency_id: str = agency_config["id"]
        self.agency_name: str = agency_config["name"]
        self.county: str | None = agency_config.get("county")
        self.logger = logging.getLogger(f"{__name__}.{self.agency_id}")

    @abstractmethod
    def scrape(
        self,
        keywords: list[str] | None = None,
        max_jobs: int | None = None,
    ) -> list[RawJob]:
        """
        Fetch current open job postings for this agency.

        Args:
            keywords: Optional list of keyword filters (OR-matched against title/desc).
            max_jobs: Stop after collecting this many postings (None = all).

        Returns:
            List of normalised RawJob objects.
        """
        ...

    # ── Shared parsing helpers ──────────────────────────────────────────────

    def _parse_date(self, value: Any) -> datetime | None:
        if not value:
            return None
        if isinstance(value, datetime):
            return value
        text = str(value).strip()
        for fmt in (
            "%Y-%m-%dT%H:%M:%S.%f",
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%d",
            "%m/%d/%Y",
            "%m/%d/%Y %I:%M %p",
            "%b %d, %Y",
            "%B %d, %Y",
        ):
            try:
                return datetime.strptime(text[: len(fmt) + 6], fmt)
            except ValueError:
                continue
        return None

    @staticmethod
    def _parse_salary(value: Any) -> tuple[float | None, float | None]:
        """Parse a salary string like '$45,000.00 - $72,113.60 Annually' → (min, max)."""
        import re

        if not value:
            return None, None
        nums = re.findall(r"[\d,]+(?:\.\d+)?", str(value))
        cleaned: list[float] = []
        for n in nums:
            try:
                cleaned.append(float(n.replace(",", "")))
            except ValueError:
                continue
        # Filter out obviously-non-salary small numbers when an hourly/annual range exists
        cleaned = [c for c in cleaned if c >= 1]
        if not cleaned:
            return None, None
        if len(cleaned) == 1:
            return cleaned[0], cleaned[0]
        return min(cleaned), max(cleaned)
