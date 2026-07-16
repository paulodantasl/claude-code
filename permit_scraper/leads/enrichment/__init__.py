"""
Contact enrichment for issued-permit leads.

Augments the GC-of-record and owner contact info that came off the permit with
public data sources:

  * FL DBPR (MyFloridaLicense) — GC business address, license type/status/expiry
  * County property appraiser  — owner mailing address

    from permit_scraper.leads.enrichment import build_enrichment_manager, EnrichmentConfig

    mgr = build_enrichment_manager(EnrichmentConfig.from_dict(cfg))
    if mgr:
        mgr.enrich_lead(lead)   # fills empty fields in place
        mgr.save()              # persist the cache
"""
from .appraiser import PropertyAppraiserEnricher
from .base import (
    Enricher,
    EnrichmentCache,
    EnrichmentConfig,
    EnrichmentResult,
    merge_into_lead,
)
from .dbpr import DBPRDataFileEnricher, DBPRWebEnricher
from .manager import EnrichmentManager, build_enrichment_manager

__all__ = [
    "Enricher",
    "EnrichmentResult",
    "EnrichmentConfig",
    "EnrichmentCache",
    "merge_into_lead",
    "DBPRDataFileEnricher",
    "DBPRWebEnricher",
    "PropertyAppraiserEnricher",
    "EnrichmentManager",
    "build_enrichment_manager",
]
