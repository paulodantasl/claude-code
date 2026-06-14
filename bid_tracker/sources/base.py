"""Abstract base class for all opportunity sources."""
from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class RawDocument:
    """A solicitation attachment (drawings, specs, forms, addenda)."""

    name: str
    url: str
    kind: str | None = None        # e.g. "spec", "drawing", "form", "addendum"


@dataclass
class RawOpportunity:
    """Normalised solicitation data before DB insert."""

    source_id: str
    source: str
    source_name: str
    solicitation_number: str | None = None
    title: str | None = None
    agency: str | None = None
    opportunity_type: str | None = None       # RFP|IFB|ITB|RFQ
    description: str | None = None
    naics_code: str | None = None
    psc_code: str | None = None
    set_aside: str | None = None
    state: str | None = None
    city: str | None = None
    zip_code: str | None = None
    estimated_value: float | None = None
    posted_date: datetime | None = None
    question_due_date: datetime | None = None
    due_date: datetime | None = None
    contact_name: str | None = None
    contact_email: str | None = None
    contact_phone: str | None = None
    source_url: str | None = None
    documents: list[RawDocument] = field(default_factory=list)
    raw_data: dict[str, Any] = field(default_factory=dict)


class BaseSource(ABC):
    """All opportunity sources implement this interface."""

    def __init__(self, source_config: dict[str, Any]):
        self.config = source_config
        self.source_id: str = source_config["id"]
        self.source_name: str = source_config["name"]
        self.logger = logging.getLogger(f"{__name__}.{self.source_id}")

    @abstractmethod
    def fetch(
        self,
        days_back: int = 7,
        keywords: list[str] | None = None,
    ) -> list[RawOpportunity]:
        """
        Fetch recently posted solicitations.

        Args:
            days_back: How many calendar days to look back.
            keywords:  Optional keyword filters passed to the source where supported.

        Returns:
            List of normalised RawOpportunity objects.
        """
        ...

    # ── shared parsing helpers ────────────────────────────────────────────

    def _parse_date(self, value: Any) -> datetime | None:
        if not value:
            return None
        if isinstance(value, datetime):
            return value
        text = str(value).strip()
        # Trim timezone offset that strptime can't handle on older Pythons
        for fmt in (
            "%Y-%m-%dT%H:%M:%S.%f%z",
            "%Y-%m-%dT%H:%M:%S%z",
            "%Y-%m-%dT%H:%M:%S.%f",
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d",
            "%m/%d/%Y %H:%M:%S",
            "%m/%d/%Y %I:%M %p",
            "%m/%d/%Y",
        ):
            try:
                dt = datetime.strptime(text, fmt)
                return dt.replace(tzinfo=None)
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
