"""
Requirements extractor.

Reads the solicitation text (and any downloaded document text passed in) and
produces a structured list of submission requirements: due dates, required
forms, bonds, insurance, licensing, page limits, and evaluation criteria.

Uses Claude when ANTHROPIC_API_KEY is set; otherwise falls back to a
heuristic checklist derived from the opportunity metadata so the package is
still useful offline.
"""
from __future__ import annotations

import json
import logging
import os
import re
from typing import Any

from ..sources.base import RawOpportunity

logger = logging.getLogger(__name__)

EXTRACTION_PROMPT = """You are a construction proposal manager reviewing a public solicitation.

Extract the SUBMISSION REQUIREMENTS as JSON with this exact shape:
{{
  "submission_method": string|null,
  "due_summary": string|null,
  "required_forms": [string],
  "bonds": [string],
  "insurance": [string],
  "licenses_certifications": [string],
  "page_or_format_limits": [string],
  "evaluation_criteria": [{{"criterion": string, "weight": string|null}}],
  "mandatory_meetings": [string],
  "submittal_checklist": [string]
}}

Return ONLY the JSON object.

Solicitation:
Title: {title}
Agency: {agency}
Type: {opportunity_type}
Due: {due_date}
Description / text:
{text}
"""


class RequirementsExtractor:
    """Builds a structured requirements profile for an opportunity."""

    def __init__(self, model: str = "claude-sonnet-4-6"):
        self.model = model

    def extract(self, opp: RawOpportunity, document_text: str = "") -> dict[str, Any]:
        if os.environ.get("ANTHROPIC_API_KEY"):
            ai = self._extract_with_claude(opp, document_text)
            if ai:
                return ai
        return self._heuristic(opp, document_text)

    def _extract_with_claude(self, opp: RawOpportunity, document_text: str) -> dict[str, Any] | None:
        try:
            from anthropic import Anthropic
        except ImportError:
            logger.warning("anthropic not installed — using heuristic requirements")
            return None

        text = f"{opp.description or ''}\n\n{document_text}".strip()[:80000]
        try:
            client = Anthropic()
            message = client.messages.create(
                model=self.model,
                max_tokens=2048,
                messages=[{
                    "role": "user",
                    "content": EXTRACTION_PROMPT.format(
                        title=opp.title or "",
                        agency=opp.agency or "",
                        opportunity_type=opp.opportunity_type or "",
                        due_date=opp.due_date.strftime("%Y-%m-%d") if opp.due_date else "TBD",
                        text=text or "(no description provided)",
                    ),
                }],
            )
            raw = "".join(b.text for b in message.content if b.type == "text")
            match = re.search(r"\{.*\}", raw, re.DOTALL)
            if match:
                return json.loads(match.group(0))
        except Exception as exc:
            logger.error("Claude requirements extraction failed: %s", exc)
        return None

    def _heuristic(self, opp: RawOpportunity, document_text: str) -> dict[str, Any]:
        """Metadata + keyword based fallback so the checklist is never empty."""
        text = f"{opp.description or ''} {document_text}".lower()

        bonds = []
        if "bid bond" in text or opp.opportunity_type in ("IFB", "ITB"):
            bonds.append("Bid bond (typically 5% of bid)")
        if "performance bond" in text or (opp.estimated_value or 0) > 100_000:
            bonds.append("Performance bond (100% of contract)")
        if "payment bond" in text:
            bonds.append("Payment bond (100% of contract)")

        insurance = [
            "Commercial General Liability",
            "Workers' Compensation",
            "Automobile Liability",
        ]
        if "builder" in text and "risk" in text:
            insurance.append("Builder's Risk")

        return {
            "submission_method": "See solicitation document",
            "due_summary": opp.due_date.strftime("%Y-%m-%d %H:%M") if opp.due_date else "See solicitation",
            "required_forms": [
                "Completed bid/proposal form",
                "W-9",
                "References / past performance",
                "Required affidavits & certifications",
            ],
            "bonds": bonds or ["Confirm bonding requirements in solicitation"],
            "insurance": insurance,
            "licenses_certifications": [
                "Active contractor license in jurisdiction",
                "Business registration / vendor registration",
            ],
            "page_or_format_limits": ["Confirm format and page limits in solicitation"],
            "evaluation_criteria": [
                {"criterion": "Price", "weight": None},
                {"criterion": "Experience / past performance", "weight": None},
                {"criterion": "Schedule", "weight": None},
            ],
            "mandatory_meetings": (
                ["Confirm pre-bid meeting date/time in solicitation"]
                if "pre-bid" in text or "pre bid" in text else []
            ),
            "submittal_checklist": [
                "Bid/proposal form completed and signed",
                "Bid bond attached (if required)",
                "Insurance certificates / acord forms",
                "License & registration copies",
                "References and project experience",
                "All addenda acknowledged",
                "Submitted before deadline via required method",
            ],
        }
