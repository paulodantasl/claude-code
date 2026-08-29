"""SQLAlchemy data models for bidding opportunities and bid packages."""
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


class Opportunity(Base):
    """A public solicitation / bidding opportunity."""

    __tablename__ = "opportunities"
    __table_args__ = (
        UniqueConstraint("source_id", "source", name="uq_opportunity_source"),
        Index("ix_opportunities_due_date", "due_date"),
        Index("ix_opportunities_qualified", "qualified"),
        Index("ix_opportunities_naics", "naics_code"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    source_id: Mapped[str] = mapped_column(String(160))          # ID in the source system
    source: Mapped[str] = mapped_column(String(64))             # e.g. "sam_gov"
    source_name: Mapped[str] = mapped_column(String(160))

    # Core solicitation fields
    solicitation_number: Mapped[Optional[str]] = mapped_column(String(128))
    title: Mapped[Optional[str]] = mapped_column(String(512))
    agency: Mapped[Optional[str]] = mapped_column(String(256))
    opportunity_type: Mapped[Optional[str]] = mapped_column(String(64))   # RFP|IFB|ITB|RFQ
    description: Mapped[Optional[str]] = mapped_column(Text)

    # Classification
    naics_code: Mapped[Optional[str]] = mapped_column(String(16))
    psc_code: Mapped[Optional[str]] = mapped_column(String(16))
    set_aside: Mapped[Optional[str]] = mapped_column(String(128))

    # Place of performance
    state: Mapped[Optional[str]] = mapped_column(String(8))
    city: Mapped[Optional[str]] = mapped_column(String(128))
    zip_code: Mapped[Optional[str]] = mapped_column(String(16))

    # Financials
    estimated_value: Mapped[Optional[float]] = mapped_column(Float)

    # Key dates
    posted_date: Mapped[Optional[datetime]] = mapped_column(DateTime)
    question_due_date: Mapped[Optional[datetime]] = mapped_column(DateTime)
    due_date: Mapped[Optional[datetime]] = mapped_column(DateTime)

    # Point of contact
    contact_name: Mapped[Optional[str]] = mapped_column(String(256))
    contact_email: Mapped[Optional[str]] = mapped_column(String(256))
    contact_phone: Mapped[Optional[str]] = mapped_column(String(64))

    # Qualification
    qualified: Mapped[bool] = mapped_column(Boolean, default=False)
    qual_score: Mapped[Optional[float]] = mapped_column(Float)        # 0–100
    qual_reasons: Mapped[Optional[str]] = mapped_column(Text)         # JSON list of strings
    disqualifiers: Mapped[Optional[str]] = mapped_column(Text)        # JSON list of strings

    # Workflow
    status: Mapped[str] = mapped_column(String(32), default="new")    # new|qualified|packaged|skipped
    package_path: Mapped[Optional[str]] = mapped_column(Text)
    proposal_drafted: Mapped[bool] = mapped_column(Boolean, default=False)
    alert_sent: Mapped[bool] = mapped_column(Boolean, default=False)

    # Source reference
    source_url: Mapped[Optional[str]] = mapped_column(Text)
    documents: Mapped[Optional[str]] = mapped_column(Text)            # JSON list of {name,url}

    # Metadata
    scraped_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    raw_data: Mapped[Optional[str]] = mapped_column(Text)             # JSON blob of original

    def __repr__(self) -> str:
        return f"<Opportunity {self.solicitation_number} | {self.title} | {self.agency}>"


class SourceRun(Base):
    """Log of each source pull for monitoring."""

    __tablename__ = "source_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    source: Mapped[str] = mapped_column(String(64))
    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    records_found: Mapped[int] = mapped_column(Integer, default=0)
    records_new: Mapped[int] = mapped_column(Integer, default=0)
    records_qualified: Mapped[int] = mapped_column(Integer, default=0)
    packages_built: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(32), default="running")   # running|success|error
    error_message: Mapped[Optional[str]] = mapped_column(Text)
