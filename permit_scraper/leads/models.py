"""
Data models for the issued-permit lead-generation feature.

A **Lead** is a permit that has reached ISSUED status and matches your scope
(commercial + residential projects), turned into an outreach record keyed on the
two people you'd pitch: the **general contractor of record** and the **owner**.

Plain dataclasses only — no SQLAlchemy — so the lead pipeline runs as a
lightweight script and is fully testable without a database.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


def utcnow_iso() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


@dataclass
class LeadConfig:
    """Controls which issued permits become leads."""

    # Categories to include (a permit is categorised from its type/description).
    include_categories: list[str] = field(
        default_factory=lambda: ["commercial", "residential", "industrial"]
    )
    # Normalised lifecycle phases that qualify (default: only 'issued').
    qualifying_phases: list[str] = field(default_factory=lambda: ["issued"])
    # Permit-type / description keywords that mark a permit as low-value "noise"
    # (standalone trade permits you don't want as GC/owner leads).
    exclude_keywords: list[str] = field(default_factory=list)
    # Minimum estimated value per category (None = no floor).
    min_value: dict[str, float] = field(default_factory=dict)
    # Only surface permits issued within this many days (None = no recency gate).
    issued_within_days: int | None = None
    # Raw contact-enrichment config block (parsed by leads.enrichment).
    enrichment: dict = field(default_factory=dict)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "LeadConfig":
        d = d or {}
        return cls(
            include_categories=d.get("include_categories")
            or ["commercial", "residential", "industrial"],
            qualifying_phases=d.get("qualifying_phases") or ["issued"],
            exclude_keywords=d.get("exclude_keywords") or list(DEFAULT_EXCLUDE_KEYWORDS),
            min_value=d.get("min_value") or {},
            issued_within_days=d.get("issued_within_days"),
            enrichment=d.get("enrichment") or {},
        )


# Standalone trade / low-value permits that are NOT good GC/owner leads.
DEFAULT_EXCLUDE_KEYWORDS: tuple[str, ...] = (
    "reroof", "re-roof", "roof over", "roofing", "roof only",
    "water heater", "hvac change", "a/c change", "ac change out", "mechanical change",
    "window", "door replacement", "shutter", "impact window",
    "fence", "pool", "spa", "screen enclosure", "screen room", "lanai",
    "sign", "signage", "awning",
    "solar", "photovoltaic", " pv ", "generator", "lp tank", "gas tank",
    "irrigation", "driveway", "paver", "shed", "utility shed",
    "demolition", "demo only", "electrical only", "plumbing only",
    "low voltage", "alarm", "security", "tent", "temporary",
    "re-pipe", "repipe", "gas piping", "propane",
)


@dataclass
class Lead:
    """An issued-permit sales lead (one project = one opportunity)."""

    lead_id: str                       # <county>::<permit_number|source_id>
    source: str
    county_id: str
    county_name: str | None
    permit_number: str | None
    permit_type: str | None
    category: str | None               # commercial | residential | industrial
    description: str | None
    status: str | None
    issued_date: str | None
    # Project location
    project_address: str | None
    city: str | None
    state: str | None
    zip_code: str | None
    parcel_number: str | None
    estimated_value: float | None
    total_sqft: float | None
    # Contact #1 — general contractor of record
    gc_name: str | None
    gc_license: str | None
    gc_phone: str | None
    # Contact #2 — owner
    owner_name: str | None
    owner_mailing_address: str | None
    owner_phone: str | None
    applicant_name: str | None
    portal_url: str | None
    first_seen: str = field(default_factory=utcnow_iso)
    lead_status: str = "new"
    # ── Enrichment (DBPR / property appraiser) — filled when enabled ──
    gc_address: str | None = None            # GC business address (DBPR)
    gc_license_status: str | None = None     # e.g. "Current, Active" (DBPR)
    gc_license_type: str | None = None       # e.g. "Certified General Contractor"
    gc_license_expiry: str | None = None     # license expiration date (DBPR)
    gc_email: str | None = None
    enriched_from: list[str] = field(default_factory=list)  # which sources contributed

    def to_dict(self) -> dict[str, Any]:
        return {k: getattr(self, k) for k in LEAD_FIELDS}


# Canonical column order for CSV / Sheets (sales call-list layout).
LEAD_FIELDS: list[str] = [
    "issued_date",
    "permit_number",
    "category",
    "county_name",
    "project_address",
    "city",
    "zip_code",
    "permit_type",
    "description",
    "estimated_value",
    "total_sqft",
    "gc_name",
    "gc_license",
    "gc_license_type",
    "gc_license_status",
    "gc_license_expiry",
    "gc_phone",
    "gc_address",
    "gc_email",
    "owner_name",
    "owner_mailing_address",
    "owner_phone",
    "applicant_name",
    "parcel_number",
    "portal_url",
    "enriched_from",
    "lead_status",
    "first_seen",
    "lead_id",
    "county_id",
    "source",
    "state",
    "status",
]
