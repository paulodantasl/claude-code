"""
Opportunity qualifier.

Scores each solicitation against the company's bid/no-bid criteria and decides
whether it is worth pursuing. Two layers:

1. Hard filters (disqualifiers): geography, response window too short, value over
   bonding capacity, excluded keywords. Any hit → not qualified.
2. Weighted score (0–100): NAICS match, project-type keywords, contract value
   sweet spot, set-aside eligibility, and geography preference. Qualifies when
   the score clears the configured threshold.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from ..sources.base import RawOpportunity

logger = logging.getLogger(__name__)


@dataclass
class QualificationResult:
    qualified: bool
    score: float                       # 0–100
    reasons: list[str] = field(default_factory=list)
    disqualifiers: list[str] = field(default_factory=list)


class Qualifier:
    """Applies the company's bid/no-bid criteria to an opportunity."""

    DEFAULT_WEIGHTS = {
        "naics": 30,
        "keywords": 25,
        "value": 20,
        "geography": 15,
        "set_aside": 10,
    }

    def __init__(self, criteria: dict[str, Any]):
        self.criteria = criteria or {}
        self.naics_codes = [str(n) for n in self.criteria.get("naics_codes", [])]
        self.keywords_include = [k.lower() for k in self.criteria.get("keywords_include", [])]
        self.keywords_exclude = [k.lower() for k in self.criteria.get("keywords_exclude", [])]
        self.states = [s.upper() for s in self.criteria.get("states", [])]
        self.min_value = self.criteria.get("min_value")
        self.max_value = self.criteria.get("max_value")
        self.bonding_capacity = self.criteria.get("bonding_capacity")
        self.set_asides = [s.lower() for s in self.criteria.get("set_asides", [])]
        self.min_days_to_respond = int(self.criteria.get("min_days_to_respond", 0))
        self.threshold = float(self.criteria.get("score_threshold", 60))
        self.weights = {**self.DEFAULT_WEIGHTS, **self.criteria.get("weights", {})}

    def qualify(self, opp: RawOpportunity) -> QualificationResult:
        disq = self._disqualifiers(opp)
        if disq:
            return QualificationResult(qualified=False, score=0.0, disqualifiers=disq)

        score, reasons = self._score(opp)
        return QualificationResult(
            qualified=score >= self.threshold,
            score=round(score, 1),
            reasons=reasons,
        )

    # ── hard filters ──────────────────────────────────────────────────────

    def _disqualifiers(self, opp: RawOpportunity) -> list[str]:
        out: list[str] = []
        text = f"{opp.title or ''} {opp.description or ''}".lower()

        if self.states and opp.state and opp.state.upper() not in self.states:
            out.append(f"Outside target states ({opp.state})")

        for kw in self.keywords_exclude:
            if kw in text:
                out.append(f"Excluded keyword present: '{kw}'")

        if self.bonding_capacity and opp.estimated_value and opp.estimated_value > self.bonding_capacity:
            out.append(
                f"Est. value ${opp.estimated_value:,.0f} exceeds bonding capacity "
                f"${self.bonding_capacity:,.0f}"
            )

        if self.min_days_to_respond and opp.due_date:
            days = (opp.due_date - datetime.utcnow()).days
            if days < self.min_days_to_respond:
                out.append(f"Only {days} days to respond (min {self.min_days_to_respond})")

        return out

    # ── weighted scoring ──────────────────────────────────────────────────

    def _score(self, opp: RawOpportunity) -> tuple[float, list[str]]:
        reasons: list[str] = []
        earned = 0.0
        total = sum(self.weights.values()) or 1

        # NAICS
        if self.naics_codes:
            if opp.naics_code and any(opp.naics_code.startswith(n) for n in self.naics_codes):
                earned += self.weights["naics"]
                reasons.append(f"NAICS {opp.naics_code} matches target sectors")
        else:
            earned += self.weights["naics"]   # no NAICS filter configured → neutral credit

        # Keywords
        text = f"{opp.title or ''} {opp.description or ''}".lower()
        hits = [k for k in self.keywords_include if k in text]
        if self.keywords_include:
            if hits:
                fraction = min(1.0, len(hits) / max(1, min(3, len(self.keywords_include))))
                earned += self.weights["keywords"] * fraction
                reasons.append(f"Matched keywords: {', '.join(hits[:5])}")
        else:
            earned += self.weights["keywords"]

        # Value sweet spot
        if opp.estimated_value is not None and (self.min_value or self.max_value):
            lo = self.min_value or 0
            hi = self.max_value or float("inf")
            if lo <= opp.estimated_value <= hi:
                earned += self.weights["value"]
                reasons.append(f"Est. value ${opp.estimated_value:,.0f} within target range")
            elif opp.estimated_value < lo:
                earned += self.weights["value"] * 0.3
                reasons.append("Est. value below preferred range (partial credit)")
        else:
            earned += self.weights["value"] * 0.5   # unknown value → partial credit

        # Geography preference
        if self.states:
            if opp.state and opp.state.upper() in self.states:
                earned += self.weights["geography"]
                reasons.append(f"In target state {opp.state}")
        else:
            earned += self.weights["geography"]

        # Set-aside eligibility
        if self.set_asides:
            sa = (opp.set_aside or "").lower()
            if sa and any(s in sa for s in self.set_asides):
                earned += self.weights["set_aside"]
                reasons.append(f"Eligible set-aside: {opp.set_aside}")
            elif not sa:
                earned += self.weights["set_aside"] * 0.5   # full & open → still biddable
        else:
            earned += self.weights["set_aside"]

        return (earned / total) * 100.0, reasons
