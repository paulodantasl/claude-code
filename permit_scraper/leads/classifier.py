"""
Decide which issued permits become leads, and turn a qualifying permit into a
:class:`Lead` with the GC-of-record and owner as the two outreach contacts.

Qualification (all must hold):
  1. status normalises to a qualifying phase (default: ``issued``)
  2. the permit categorises into an included category (commercial / residential
     / industrial)
  3. it is not a standalone low-value trade permit (exclude-keyword list)
  4. its estimated value clears the per-category floor, if one is set
  5. it was issued within the recency window, if one is set
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any

from ..monitoring.status import normalize
from ..scrapers.base import RawPermit
from .models import Lead, LeadConfig

logger = logging.getLogger(__name__)

_RESIDENTIAL_KW = (
    "residential", "single family", "single-family", "sfr", "dwelling",
    "townhouse", "townhome", "duplex", "triplex", "condo", "apartment",
    "multifamily", "multi-family", "new home", "custom home", "1-family",
    "2-family", "accessory dwelling", "adu",
)
_INDUSTRIAL_KW = (
    "warehouse", "distribution", "industrial", "manufacturing", "logistics",
    "data center", "cold storage", "fulfillment",
)
_COMMERCIAL_KW = (
    "commercial", "retail", "store", "shop", "restaurant", "office", "medical",
    "pharmacy", "grocery", "supermarket", "hotel", "motel", "mixed use",
    "mixed-use", "tenant improvement", "tenant build", "build-out", "buildout",
    "shell", "core and shell", "business",
)
# Permit-type words that indicate a substantial *project* (keeps new
# construction / additions / major alterations even if the description is thin).
_PROJECT_KW = (
    "new construction", "new building", "addition", "alteration", "remodel",
    "renovation", "tenant improvement", "build-out", "buildout", "shell",
)


class LeadClassifier:
    """Qualifies issued permits and builds Lead records."""

    def __init__(self, config: LeadConfig | None = None):
        self.config = config or LeadConfig()

    # ── Categorisation ──────────────────────────────────────────────────────

    @staticmethod
    def categorize(permit: RawPermit) -> str:
        text = f"{permit.permit_type or ''} {permit.description or ''}".lower()
        if any(kw in text for kw in _INDUSTRIAL_KW):
            return "industrial"
        # Residential is checked before commercial because "residential" is a
        # strong explicit signal; mixed hits fall through to commercial.
        if any(kw in text for kw in _RESIDENTIAL_KW):
            return "residential"
        if any(kw in text for kw in _COMMERCIAL_KW):
            return "commercial"
        return "unknown"

    def is_noise(self, permit: RawPermit) -> bool:
        text = f"{permit.permit_type or ''} {permit.description or ''}".lower()
        # A permit that also names a real project scope is kept even if it
        # mentions a trade word (e.g. "New Construction w/ roof & mechanical").
        if any(kw in text for kw in _PROJECT_KW):
            return False
        return any(kw in text for kw in self.config.exclude_keywords)

    def _issued_recent(self, permit: RawPermit) -> bool:
        window = self.config.issued_within_days
        if not window:
            return True
        if not permit.issued_date:
            return True  # unknown issue date — don't drop it
        issued = permit.issued_date
        if not isinstance(issued, datetime):
            return True
        return issued >= datetime.utcnow() - timedelta(days=window)

    # ── Qualification ───────────────────────────────────────────────────────

    def qualifies(self, permit: RawPermit) -> tuple[bool, str]:
        """Return (qualifies, reason-if-not)."""
        phase = normalize(permit.status).value
        if phase not in self.config.qualifying_phases:
            return False, f"phase '{phase}' not in {self.config.qualifying_phases}"

        category = self.categorize(permit)
        if category not in self.config.include_categories:
            return False, f"category '{category}' excluded"

        if self.is_noise(permit):
            return False, "matched exclude-keyword (trade/low-value permit)"

        floor = self.config.min_value.get(category)
        if floor is not None and (permit.estimated_value or 0) < floor:
            return False, f"value {permit.estimated_value} below {category} floor {floor}"

        if not self._issued_recent(permit):
            return False, "issued outside recency window"

        return True, ""

    # ── Lead construction ───────────────────────────────────────────────────

    def build_lead(self, permit: RawPermit) -> Lead:
        category = self.categorize(permit)
        raw = permit.raw_data or {}
        return Lead(
            lead_id=self._lead_id(permit),
            source="permit_issued",
            county_id=permit.county_id,
            county_name=permit.county_name,
            permit_number=permit.permit_number,
            permit_type=permit.permit_type,
            category=category,
            description=permit.description,
            status=permit.status,
            issued_date=_iso(permit.issued_date),
            project_address=permit.address,
            city=permit.city,
            state=permit.state,
            zip_code=permit.zip_code,
            parcel_number=permit.parcel_number,
            estimated_value=permit.estimated_value,
            total_sqft=permit.total_sqft,
            gc_name=permit.contractor_name,
            gc_license=permit.contractor_license or _scan(raw, ("license", "state license")),
            gc_phone=permit.contractor_phone or _scan(raw, ("contractor phone", "phone")),
            owner_name=permit.owner_name,
            owner_mailing_address=permit.owner_mailing_address
            or _scan(raw, ("owner mailing", "owner address", "mailing address")),
            owner_phone=permit.owner_phone or _scan(raw, ("owner phone",)),
            applicant_name=permit.applicant_name,
            portal_url=permit.source_url,
        )

    @staticmethod
    def _lead_id(permit: RawPermit) -> str:
        ident = permit.permit_number or permit.source_id
        return f"{permit.county_id}::{ident}"


def _iso(value: Any) -> str | None:
    if value is None:
        return None
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


def _scan(raw: dict, keys: tuple[str, ...]) -> str | None:
    """Best-effort scan of a permit's raw_data for a labelled field."""
    if not isinstance(raw, dict):
        return None
    lowered = {str(k).lower(): v for k, v in raw.items()}
    for want in keys:
        for k, v in lowered.items():
            if want in k and v:
                return str(v)
    return None
