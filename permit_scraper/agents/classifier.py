"""
Company matcher and permit classifier.

Uses fuzzy string matching to find which company on the watch list
appears in a permit's applicant/owner/contractor/description fields.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Any

from fuzzywuzzy import fuzz, process

from ..scrapers.base import RawPermit

logger = logging.getLogger(__name__)


@dataclass
class MatchResult:
    company_id: str
    company_name: str
    score: float          # 0–100
    matched_field: str    # which field triggered the match
    matched_value: str    # the actual string that matched


class CompanyMatcher:
    """
    Matches permit records against a watch list of companies.

    Strategy:
    1. Exact substring match (fast, high precision).
    2. Fuzzy match on each company alias using token_set_ratio (handles
       abbreviations and word order).
    3. DBA / trade-name lookup for subsidiaries (e.g. Vadata → Amazon).
    """

    DEFAULT_THRESHOLD = 85      # minimum fuzzy score (0–100)

    def __init__(self, watch_list: list[dict[str, Any]], threshold: int = DEFAULT_THRESHOLD):
        self.threshold = threshold
        # Build a flat alias → company_id map
        self._alias_map: dict[str, dict] = {}
        for company in watch_list:
            for alias in [company["display_name"]] + company.get("aliases", []):
                self._alias_map[alias.upper()] = company

    def match(self, permit: RawPermit) -> MatchResult | None:
        """Return the best company match for a permit, or None."""
        fields = {
            "applicant_name": permit.applicant_name,
            "owner_name": permit.owner_name,
            "contractor_name": permit.contractor_name,
            "description": permit.description,
        }

        best: MatchResult | None = None

        for field_name, value in fields.items():
            if not value:
                continue
            result = self._match_value(value, field_name)
            if result and (best is None or result.score > best.score):
                best = result

        return best

    def match_value_str(self, value: str) -> MatchResult | None:
        """Public single-string match (used by property appraiser cross-reference)."""
        return self._match_value(value, "owner_name") if value else None

    def _match_value(self, value: str, field_name: str) -> MatchResult | None:
        upper = value.upper()

        # 1. Exact substring check (fastest path)
        for alias, company in self._alias_map.items():
            if alias in upper:
                return MatchResult(
                    company_id=company["id"],
                    company_name=company["display_name"],
                    score=100.0,
                    matched_field=field_name,
                    matched_value=value,
                )

        # 2. Fuzzy match against all known aliases
        aliases = list(self._alias_map.keys())
        if not aliases:
            return None

        best_alias, best_score = process.extractOne(
            upper, aliases, scorer=fuzz.token_set_ratio
        )

        if best_score >= self.threshold:
            company = self._alias_map[best_alias]
            return MatchResult(
                company_id=company["id"],
                company_name=company["display_name"],
                score=float(best_score),
                matched_field=field_name,
                matched_value=value,
            )

        return None


class PermitClassifier:
    """
    Enriches RawPermit records with:
    - Company match
    - Permit type normalisation
    - Commercial/industrial flag
    """

    COMMERCIAL_KEYWORDS = {
        "commercial", "retail", "store", "shop", "restaurant", "fast food",
        "office", "medical", "pharmacy", "grocery", "supermarket",
    }
    INDUSTRIAL_KEYWORDS = {
        "warehouse", "distribution", "industrial", "manufacturing",
        "logistics", "data center", "storage",
    }
    SKIP_TYPES = {
        "residential", "single family", "duplex", "townhouse", "condo",
        "single-family", "1-family", "sfr",
    }

    def __init__(self, matcher: CompanyMatcher):
        self.matcher = matcher

    def classify(self, permit: RawPermit) -> dict[str, Any]:
        """Return enrichment dict to merge into the DB record."""
        enrichment: dict[str, Any] = {
            "matched_company_id": None,
            "matched_company_name": None,
            "match_score": None,
            "is_commercial": False,
            "is_industrial": False,
            "skip": False,
        }

        # Normalise permit type
        ptype = (permit.permit_type or "").lower()
        desc = (permit.description or "").lower()
        combined = f"{ptype} {desc}"

        # Skip purely residential permits unless specifically requested
        if any(kw in combined for kw in self.SKIP_TYPES):
            enrichment["skip"] = True

        enrichment["is_commercial"] = any(kw in combined for kw in self.COMMERCIAL_KEYWORDS)
        enrichment["is_industrial"] = any(kw in combined for kw in self.INDUSTRIAL_KEYWORDS)

        # Company match
        match = self.matcher.match(permit)
        if match:
            enrichment["matched_company_id"] = match.company_id
            enrichment["matched_company_name"] = match.company_name
            enrichment["match_score"] = match.score
            logger.info(
                "MATCH [%.0f%%] %s → %s | %s @ %s",
                match.score,
                match.matched_value,
                match.company_name,
                permit.permit_number,
                permit.address,
            )

        return enrichment
