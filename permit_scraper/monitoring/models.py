"""
Data models for the permit-monitoring feature.

These are plain dataclasses (no SQLAlchemy dependency) so the monitor can run as
a lightweight standalone script with only stdlib + PyYAML + requests. State is
persisted as JSON by :mod:`permit_scraper.monitoring.state_store`.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from .status import Phase


# ── Configuration objects (loaded from YAML) ────────────────────────────────


@dataclass
class FieldManager:
    """A field manager who receives permit notifications."""

    id: str
    name: str
    email: str | None = None
    phone: str | None = None                 # E.164, e.g. +13055551234 (for SMS)
    slack_webhook: str | None = None         # optional per-manager Slack webhook
    channels: list[str] = field(default_factory=lambda: ["console"])
    active: bool = True

    def __repr__(self) -> str:  # pragma: no cover - cosmetic
        return f"<FieldManager {self.id} ({self.name})>"


@dataclass
class TrackedPermit:
    """A single pending permit / project we are monitoring for updates."""

    permit_number: str
    county: str                              # county id (must exist in counties.yaml)
    project_name: str | None = None
    address: str | None = None
    category: str | None = None              # "residential" | "commercial"
    manager_ids: list[str] = field(default_factory=list)
    watch_fields: list[str] = field(default_factory=list)  # extra raw_data keys to watch
    source_url: str | None = None
    active: bool = True
    notes: str | None = None

    @property
    def key(self) -> str:
        """Stable identity for state storage: ``<county>::<permit_number>``."""
        return f"{self.county}::{self.permit_number}"

    @property
    def label(self) -> str:
        """Human label for messages."""
        return self.project_name or self.address or self.permit_number


# ── Runtime objects ─────────────────────────────────────────────────────────


@dataclass
class Snapshot:
    """The last-known state of a tracked permit, persisted between runs."""

    permit_key: str
    status: str | None = None
    phase: str = Phase.UNKNOWN.value
    issued_date: str | None = None
    expiry_date: str | None = None
    description: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)   # watched raw_data fields
    source_url: str | None = None
    last_seen_at: str | None = None
    last_changed_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "permit_key": self.permit_key,
            "status": self.status,
            "phase": self.phase,
            "issued_date": self.issued_date,
            "expiry_date": self.expiry_date,
            "description": self.description,
            "extra": self.extra,
            "source_url": self.source_url,
            "last_seen_at": self.last_seen_at,
            "last_changed_at": self.last_changed_at,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Snapshot":
        return cls(
            permit_key=d["permit_key"],
            status=d.get("status"),
            phase=d.get("phase", Phase.UNKNOWN.value),
            issued_date=d.get("issued_date"),
            expiry_date=d.get("expiry_date"),
            description=d.get("description"),
            extra=d.get("extra") or {},
            source_url=d.get("source_url"),
            last_seen_at=d.get("last_seen_at"),
            last_changed_at=d.get("last_changed_at"),
        )


@dataclass
class FieldChange:
    """A single field that changed between two snapshots."""

    field: str
    old: Any
    new: Any

    def to_dict(self) -> dict[str, Any]:
        return {"field": self.field, "old": self.old, "new": self.new}


@dataclass
class StatusEvent:
    """A detected update on a tracked permit — the unit that gets notified."""

    permit_key: str
    permit_number: str
    county: str
    county_name: str | None
    project_name: str | None
    category: str | None
    changes: list[FieldChange]
    old_status: str | None
    new_status: str | None
    old_phase: str
    new_phase: str
    direction: str
    priority: str                            # "high" | "normal"
    detected_at: str
    source_url: str | None
    manager_ids: list[str]
    notified: bool = False
    notify_results: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "permit_key": self.permit_key,
            "permit_number": self.permit_number,
            "county": self.county,
            "county_name": self.county_name,
            "project_name": self.project_name,
            "category": self.category,
            "changes": [c.to_dict() for c in self.changes],
            "old_status": self.old_status,
            "new_status": self.new_status,
            "old_phase": self.old_phase,
            "new_phase": self.new_phase,
            "direction": self.direction,
            "priority": self.priority,
            "detected_at": self.detected_at,
            "source_url": self.source_url,
            "manager_ids": self.manager_ids,
            "notified": self.notified,
            "notify_results": self.notify_results,
        }


def utcnow_iso() -> str:
    """UTC timestamp in ISO-8601 with a trailing Z (matches the rest of pkg)."""
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"
