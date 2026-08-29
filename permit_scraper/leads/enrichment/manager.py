"""
EnrichmentManager — run the enabled enrichers over a lead, with caching and
polite rate-limiting, and merge the results in.

Order matters: data already on the permit wins, then each enricher fills what's
still missing (DBPR for the GC, property appraiser for the owner). A persistent
cache means a repeated GC/parcel is looked up once across all runs.
"""
from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Callable

from .appraiser import PropertyAppraiserEnricher
from .base import (
    Enricher,
    EnrichmentCache,
    EnrichmentConfig,
    EnrichmentResult,
    merge_into_lead,
)
from .dbpr import DBPRDataFileEnricher, DBPRWebEnricher

logger = logging.getLogger(__name__)


class EnrichmentManager:
    """Coordinates enrichers, caching, and rate limiting."""

    def __init__(
        self,
        enrichers: list[Enricher] | None = None,
        cache: EnrichmentCache | None = None,
        rate_limit_seconds: float = 0.0,
        sleep_fn: Callable[[float], None] = time.sleep,
    ):
        self.enrichers = enrichers or []
        self.cache = cache or EnrichmentCache()
        self.rate_limit_seconds = rate_limit_seconds
        self._sleep = sleep_fn
        # Track live lookups so rate limiting only applies to cache misses.
        self.lookups = 0
        self.cache_hits = 0

    def enrich_lead(self, lead) -> bool:
        """Enrich a single lead in place. Returns True if anything was filled."""
        changed = False
        for enricher in self.enrichers:
            key = enricher.cache_key(lead)
            if key is None:
                continue
            cache_key = f"{enricher.name}:{key}"

            cached = self.cache.get(cache_key)
            if cached is not None:
                self.cache_hits += 1
                result = cached
            else:
                if self.rate_limit_seconds and self.lookups > 0:
                    self._sleep(self.rate_limit_seconds)
                try:
                    result = enricher.enrich(lead)
                except Exception as exc:  # never let one source break the lead
                    logger.error("Enricher %s failed: %s", enricher.name, exc)
                    result = EnrichmentResult(source=enricher.name)
                self.lookups += 1
                self.cache.put(cache_key, result)

            if merge_into_lead(lead, result):
                changed = True
        return changed

    def save(self) -> None:
        self.cache.save()


def build_enrichment_manager(
    config: EnrichmentConfig,
    config_dir: str | Path | None = None,
    force_enable: bool = False,
) -> EnrichmentManager | None:
    """Construct a manager from an :class:`EnrichmentConfig`, or None if disabled."""
    if not (config.enabled or force_enable):
        return None

    enrichers: list[Enricher] = []
    rate = 0.0

    # ── DBPR (GC) ────────────────────────────────────────────────────────────
    dbpr = config.dbpr or {}
    if dbpr.get("enabled", bool(dbpr)):
        mode = dbpr.get("mode", "data_file")
        if mode == "data_file" and dbpr.get("data_file"):
            enrichers.append(
                DBPRDataFileEnricher(
                    data_file=dbpr["data_file"],
                    column_overrides=dbpr.get("columns"),
                )
            )
        elif mode == "web":
            enrichers.append(DBPRWebEnricher(timeout=dbpr.get("timeout", 20)))
            rate = max(rate, float(dbpr.get("rate_limit_seconds", 1.5)))
        elif mode == "data_file":
            logger.warning("DBPR data_file mode selected but no 'data_file' path set — skipping DBPR")

    # ── Property appraiser (owner) ───────────────────────────────────────────
    appr = config.appraiser or {}
    if appr.get("enabled", bool(appr)):
        enrichers.append(PropertyAppraiserEnricher(counties=appr.get("counties")))
        rate = max(rate, float(appr.get("rate_limit_seconds", 1.0)))

    if not enrichers:
        logger.info("Enrichment enabled but no sources configured")
        return None

    cache = EnrichmentCache(config.cache_file)
    return EnrichmentManager(enrichers=enrichers, cache=cache, rate_limit_seconds=rate)
