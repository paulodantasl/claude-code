"""SQLAlchemy data models for job postings and the review queue."""
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


class Job(Base):
    """A scraped government job posting, with its computed fit score."""

    __tablename__ = "jobs"
    __table_args__ = (
        UniqueConstraint("source_id", name="uq_job_source"),
        Index("ix_jobs_agency", "agency_id"),
        Index("ix_jobs_county", "county"),
        Index("ix_jobs_score", "fit_score"),
        Index("ix_jobs_closing", "closing_date"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    source_id: Mapped[str] = mapped_column(String(160))

    agency_id: Mapped[str] = mapped_column(String(64))
    agency_name: Mapped[str] = mapped_column(String(160))
    county: Mapped[Optional[str]] = mapped_column(String(32))

    title: Mapped[Optional[str]] = mapped_column(String(256))
    department: Mapped[Optional[str]] = mapped_column(String(160))
    category: Mapped[Optional[str]] = mapped_column(String(128))
    job_type: Mapped[Optional[str]] = mapped_column(String(64))
    location: Mapped[Optional[str]] = mapped_column(String(160))
    salary_min: Mapped[Optional[float]] = mapped_column(Float)
    salary_max: Mapped[Optional[float]] = mapped_column(Float)
    salary_raw: Mapped[Optional[str]] = mapped_column(String(160))

    description: Mapped[Optional[str]] = mapped_column(Text)
    requirements: Mapped[Optional[str]] = mapped_column(Text)

    posted_date: Mapped[Optional[datetime]] = mapped_column(DateTime)
    closing_date: Mapped[Optional[datetime]] = mapped_column(DateTime)
    job_id_external: Mapped[Optional[str]] = mapped_column(String(64))
    apply_url: Mapped[Optional[str]] = mapped_column(Text)
    source_url: Mapped[Optional[str]] = mapped_column(Text)

    # Matching
    fit_score: Mapped[Optional[float]] = mapped_column(Float)
    lexical_score: Mapped[Optional[float]] = mapped_column(Float)
    semantic_score: Mapped[Optional[float]] = mapped_column(Float)
    recommendation: Mapped[Optional[str]] = mapped_column(String(16))  # apply|maybe|skip
    matched_skills: Mapped[Optional[str]] = mapped_column(Text)        # JSON list
    gaps: Mapped[Optional[str]] = mapped_column(Text)                  # JSON list
    fit_reasons: Mapped[Optional[str]] = mapped_column(Text)

    # Review workflow
    flagged: Mapped[bool] = mapped_column(Boolean, default=False)
    packet_path: Mapped[Optional[str]] = mapped_column(Text)
    # new | flagged | prefilled | reviewed | submitted | dismissed
    review_status: Mapped[str] = mapped_column(String(24), default="new")
    alert_sent: Mapped[bool] = mapped_column(Boolean, default=False)

    scraped_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    raw_data: Mapped[Optional[str]] = mapped_column(Text)

    def __repr__(self) -> str:
        return f"<Job {self.title!r} @ {self.agency_name} fit={self.fit_score}>"


class ScraperRun(Base):
    """Log of each pipeline run for monitoring."""

    __tablename__ = "scraper_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    agency_id: Mapped[str] = mapped_column(String(64))
    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    jobs_found: Mapped[int] = mapped_column(Integer, default=0)
    jobs_new: Mapped[int] = mapped_column(Integer, default=0)
    jobs_flagged: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(32), default="running")  # running|success|error
    error_message: Mapped[Optional[str]] = mapped_column(Text)
