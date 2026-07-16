"""
Enrichment framework: augment a Lead's GC/owner contact info from external
public sources (FL DBPR licensee data, county property appraisers).

Design goals:
  * **Pluggable** — each source is an :class:`Enricher`; the manager runs the
    enabled ones and merges their results.
  * **Non-destructive** — enrichment only fills fields that are empty; data that
    came straight off the permit always wins.
  * **Cheap & polite** — a persistent cache means a GC/parcel is looked up once,
    not once per permit; live enrichers are rate-limited.
  * **Testable** — enrichers are import-light and accept injected lookups, so the
    whole path runs with no network in the demo.
"""
from __future__ import annotations

import contextlib
import json
import logging
import os
import tempfile
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class EnrichmentResult:
    """Fields a source can contribute. All optional; None = nothing found."""

    gc_phone: str | None = None
    gc_address: str | None = None
    gc_email: str | None = None
    gc_license: str | None = None
    gc_license_status: str | None = None
    gc_license_type: str | None = None
    gc_license_expiry: str | None = None
    owner_mailing_address: str | None = None
    owner_phone: str | None = None
    source: str | None = None                 # name of the contributing enricher

    def is_empty(self) -> bool:
        return not any(
            getattr(self, f) for f in (
                "gc_phone", "gc_address", "gc_email", "gc_license",
                "gc_license_status", "gc_license_type", "gc_license_expiry",
                "owner_mailing_address", "owner_phone",
            )
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "gc_phone": self.gc_phone,
            "gc_address": self.gc_address,
            "gc_email": self.gc_email,
            "gc_license": self.gc_license,
            "gc_license_status": self.gc_license_status,
            "gc_license_type": self.gc_license_type,
            "gc_license_expiry": self.gc_license_expiry,
            "owner_mailing_address": self.owner_mailing_address,
            "owner_phone": self.owner_phone,
            "source": self.source,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "EnrichmentResult":
        return cls(**{k: d.get(k) for k in (
            "gc_phone", "gc_address", "gc_email", "gc_license",
            "gc_license_status", "gc_license_type", "gc_license_expiry",
            "owner_mailing_address", "owner_phone", "source",
        )})


# Lead fields an enrichment result may fill, and the result attribute it maps to.
_MERGE_MAP = {
    "gc_phone": "gc_phone",
    "gc_address": "gc_address",
    "gc_email": "gc_email",
    "gc_license": "gc_license",
    "gc_license_status": "gc_license_status",
    "gc_license_type": "gc_license_type",
    "gc_license_expiry": "gc_license_expiry",
    "owner_mailing_address": "owner_mailing_address",
    "owner_phone": "owner_phone",
}


def merge_into_lead(lead, result: EnrichmentResult) -> bool:
    """Fill empty lead fields from ``result``. Returns True if anything changed."""
    changed = False
    for lead_attr, res_attr in _MERGE_MAP.items():
        value = getattr(result, res_attr, None)
        if value and not getattr(lead, lead_attr, None):
            setattr(lead, lead_attr, value)
            changed = True
    if changed and result.source and result.source not in lead.enriched_from:
        lead.enriched_from.append(result.source)
    return changed


class Enricher(ABC):
    """A single enrichment source."""

    name: str = "enricher"

    @abstractmethod
    def cache_key(self, lead) -> str | None:
        """Stable key for caching this lead's lookup (None = can't enrich it)."""

    @abstractmethod
    def enrich(self, lead) -> EnrichmentResult:
        """Look up and return an EnrichmentResult (possibly empty)."""


@dataclass
class EnrichmentConfig:
    enabled: bool = False
    cache_file: str = "permit_leads_enrichment_cache.json"
    dbpr: dict = field(default_factory=dict)
    appraiser: dict = field(default_factory=dict)

    @classmethod
    def from_dict(cls, d: dict[str, Any] | None) -> "EnrichmentConfig":
        d = d or {}
        return cls(
            enabled=d.get("enabled", False),
            cache_file=d.get("cache_file", "permit_leads_enrichment_cache.json"),
            dbpr=d.get("dbpr", {}) or {},
            appraiser=d.get("appraiser", {}) or {},
        )


class EnrichmentCache:
    """Persistent JSON cache: ``"<enricher>:<key>" -> EnrichmentResult dict``."""

    def __init__(self, path: str | Path | None = None):
        self.path = Path(path) if path else None
        self._data: dict[str, dict] = {}
        self._loaded = False

    def load(self) -> None:
        self._data = {}
        if self.path and self.path.exists():
            try:
                self._data = json.loads(self.path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError) as exc:
                logger.error("Could not read enrichment cache %s: %s", self.path, exc)
        self._loaded = True

    def get(self, key: str) -> EnrichmentResult | None:
        if not self._loaded:
            self.load()
        d = self._data.get(key)
        return EnrichmentResult.from_dict(d) if d is not None else None

    def has(self, key: str) -> bool:
        if not self._loaded:
            self.load()
        return key in self._data

    def put(self, key: str, result: EnrichmentResult) -> None:
        if not self._loaded:
            self.load()
        self._data[key] = result.to_dict()

    def save(self) -> None:
        if not self.path:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=str(self.path.parent), suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(self._data, f, indent=2, sort_keys=True)
            os.replace(tmp, self.path)
        except Exception:
            with contextlib.suppress(OSError):
                os.unlink(tmp)
            raise
