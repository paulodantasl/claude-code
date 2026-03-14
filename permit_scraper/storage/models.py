"""SQLAlchemy data models for permit and property data."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Permit(Base):
    """A building/construction permit record."""

    __tablename__ = "permits"
    __table_args__ = (
        UniqueConstraint("source_id", "county_id", name="uq_permit_source"),
        Index("ix_permits_applicant", "applicant_name"),
        Index("ix_permits_filed_date", "filed_date"),
        Index("ix_permits_matched_company", "matched_company_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    source_id: Mapped[str] = mapped_column(String(128))          # ID from source system
    county_id: Mapped[str] = mapped_column(String(64))           # e.g. "miami_dade"
    county_name: Mapped[str] = mapped_column(String(128))

    # Core permit fields
    permit_number: Mapped[Optional[str]] = mapped_column(String(64))
    permit_type: Mapped[Optional[str]] = mapped_column(String(128))
    permit_subtype: Mapped[Optional[str]] = mapped_column(String(128))
    status: Mapped[Optional[str]] = mapped_column(String(64))
    description: Mapped[Optional[str]] = mapped_column(Text)

    # Parties
    applicant_name: Mapped[Optional[str]] = mapped_column(String(256))
    owner_name: Mapped[Optional[str]] = mapped_column(String(256))
    contractor_name: Mapped[Optional[str]] = mapped_column(String(256))

    # Location
    address: Mapped[Optional[str]] = mapped_column(String(512))
    city: Mapped[Optional[str]] = mapped_column(String(128))
    state: Mapped[Optional[str]] = mapped_column(String(8))
    zip_code: Mapped[Optional[str]] = mapped_column(String(16))
    parcel_number: Mapped[Optional[str]] = mapped_column(String(64))
    latitude: Mapped[Optional[float]] = mapped_column(Float)
    longitude: Mapped[Optional[float]] = mapped_column(Float)

    # Financials
    estimated_value: Mapped[Optional[float]] = mapped_column(Float)
    total_sqft: Mapped[Optional[float]] = mapped_column(Float)

    # Dates
    filed_date: Mapped[Optional[datetime]] = mapped_column(DateTime)
    issued_date: Mapped[Optional[datetime]] = mapped_column(DateTime)
    expiry_date: Mapped[Optional[datetime]] = mapped_column(DateTime)

    # Matching
    matched_company_id: Mapped[Optional[str]] = mapped_column(String(64))
    matched_company_name: Mapped[Optional[str]] = mapped_column(String(256))
    match_score: Mapped[Optional[float]] = mapped_column(Float)   # 0–100 fuzzy score
    alert_sent: Mapped[bool] = mapped_column(Boolean, default=False)

    # Source URL for reference
    source_url: Mapped[Optional[str]] = mapped_column(Text)

    # Metadata
    scraped_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    raw_data: Mapped[Optional[str]] = mapped_column(Text)         # JSON blob of original

    def __repr__(self) -> str:
        return f"<Permit {self.permit_number} | {self.applicant_name} | {self.address}>"


class PropertyRecord(Base):
    """A property record from the property appraiser."""

    __tablename__ = "properties"
    __table_args__ = (
        UniqueConstraint("parcel_number", "county_id", name="uq_property_parcel"),
        Index("ix_properties_owner", "owner_name"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    county_id: Mapped[str] = mapped_column(String(64))
    parcel_number: Mapped[str] = mapped_column(String(64))

    owner_name: Mapped[Optional[str]] = mapped_column(String(256))
    mailing_address: Mapped[Optional[str]] = mapped_column(String(512))
    site_address: Mapped[Optional[str]] = mapped_column(String(512))
    city: Mapped[Optional[str]] = mapped_column(String(128))
    zip_code: Mapped[Optional[str]] = mapped_column(String(16))

    land_use: Mapped[Optional[str]] = mapped_column(String(128))
    zoning: Mapped[Optional[str]] = mapped_column(String(64))
    assessed_value: Mapped[Optional[float]] = mapped_column(Float)
    land_area_sqft: Mapped[Optional[float]] = mapped_column(Float)
    building_area_sqft: Mapped[Optional[float]] = mapped_column(Float)

    # Recent sale
    last_sale_date: Mapped[Optional[datetime]] = mapped_column(DateTime)
    last_sale_price: Mapped[Optional[float]] = mapped_column(Float)

    # Matching
    matched_company_id: Mapped[Optional[str]] = mapped_column(String(64))
    matched_company_name: Mapped[Optional[str]] = mapped_column(String(256))
    match_score: Mapped[Optional[float]] = mapped_column(Float)

    scraped_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    def __repr__(self) -> str:
        return f"<Property {self.parcel_number} | {self.owner_name} | {self.site_address}>"


class ScraperRun(Base):
    """Log of each scraper run for monitoring."""

    __tablename__ = "scraper_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    county_id: Mapped[str] = mapped_column(String(64))
    scraper_type: Mapped[str] = mapped_column(String(64))
    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    records_found: Mapped[int] = mapped_column(Integer, default=0)
    records_new: Mapped[int] = mapped_column(Integer, default=0)
    records_matched: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(32), default="running")   # running|success|error
    error_message: Mapped[Optional[str]] = mapped_column(Text)
