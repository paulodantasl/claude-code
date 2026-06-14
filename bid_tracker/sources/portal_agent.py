"""
AI-assisted portal source.

For agency procurement portals that have no API or feed, this source fetches
the public solicitation-listing page and asks Claude to extract structured
opportunities from the HTML. It is the fallback used when a portal can't be
read by the API or RSS adapters.

Requires ANTHROPIC_API_KEY. Configure per portal in sources.yaml:

    - id: city_tampa_bids
      name: "City of Tampa Procurement"
      type: ai
      listing_url: "https://www.tampa.gov/purchasing/active-solicitations"
      state: FL
"""
from __future__ import annotations

import json
import logging
import os
import re
from datetime import datetime
from typing import Any

import requests
from tenacity import retry, stop_after_attempt, wait_exponential

from .base import BROWSER_USER_AGENT, BaseSource, RawDocument, RawOpportunity

logger = logging.getLogger(__name__)

EXTRACTION_PROMPT = """You are extracting public construction bidding opportunities from a \
government procurement web page.

Return ONLY a JSON array. Each element is an object with these keys (use null when unknown):
  solicitation_number, title, agency, opportunity_type (one of RFP, IFB, ITB, RFQ),
  description, naics_code, state, city, estimated_value (number, no symbols),
  posted_date (YYYY-MM-DD), due_date (YYYY-MM-DD), contact_name, contact_email,
  contact_phone, detail_url, documents (array of {{name, url}}).

Only include OPEN construction-related solicitations. Resolve relative URLs against the
base URL: {base_url}

Page text:
{page_text}
"""


class PortalAgentSource(BaseSource):
    """Uses Claude to extract opportunities from an arbitrary portal page."""

    def __init__(self, source_config: dict[str, Any]):
        super().__init__(source_config)
        self.listing_url = source_config["listing_url"]
        self.default_state = source_config.get("state")
        self.model = source_config.get("model", "claude-sonnet-4-6")

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=2, min=2, max=20))
    def _fetch_html(self) -> str:
        resp = requests.get(self.listing_url, timeout=45, headers={"User-Agent": BROWSER_USER_AGENT})
        resp.raise_for_status()
        return resp.text

    def fetch(self, days_back: int = 7, keywords: list[str] | None = None) -> list[RawOpportunity]:
        if not os.environ.get("ANTHROPIC_API_KEY"):
            self.logger.warning(
                "ANTHROPIC_API_KEY not set — skipping AI portal source %s", self.source_name
            )
            return []

        try:
            from anthropic import Anthropic
        except ImportError:
            self.logger.error("anthropic package not installed — run `pip install anthropic`")
            return []

        try:
            html = self._fetch_html()
        except Exception as exc:
            self.logger.error("Portal fetch failed for %s: %s", self.listing_url, exc)
            return []

        # Strip tags/scripts to keep the prompt compact.
        text = re.sub(r"(?is)<(script|style).*?>.*?</\1>", " ", html)
        text = re.sub(r"(?s)<[^>]+>", " ", text)
        text = re.sub(r"\s+", " ", text).strip()[:60000]

        client = Anthropic()
        try:
            message = client.messages.create(
                model=self.model,
                max_tokens=4096,
                messages=[{
                    "role": "user",
                    "content": EXTRACTION_PROMPT.format(base_url=self.listing_url, page_text=text),
                }],
            )
        except Exception as exc:
            self.logger.error("Claude extraction failed for %s: %s", self.source_name, exc)
            return []

        raw_text = "".join(block.text for block in message.content if block.type == "text")
        records = self._parse_json(raw_text)

        results = [self._normalise(rec) for rec in records if isinstance(rec, dict)]
        self.logger.info("AI portal %s returned %d opportunities", self.source_name, len(results))
        return results

    @staticmethod
    def _parse_json(text: str) -> list[dict]:
        match = re.search(r"\[.*\]", text, re.DOTALL)
        if not match:
            return []
        try:
            data = json.loads(match.group(0))
            return data if isinstance(data, list) else []
        except json.JSONDecodeError:
            return []

    def _normalise(self, rec: dict) -> RawOpportunity:
        detail_url = rec.get("detail_url") or self.listing_url
        documents = [
            RawDocument(name=d.get("name", "Attachment"), url=d["url"])
            for d in (rec.get("documents") or [])
            if isinstance(d, dict) and d.get("url")
        ]
        return RawOpportunity(
            source_id=rec.get("solicitation_number") or detail_url or rec.get("title", ""),
            source=self.source_id,
            source_name=self.source_name,
            solicitation_number=rec.get("solicitation_number"),
            title=rec.get("title"),
            agency=rec.get("agency") or self.source_name,
            opportunity_type=rec.get("opportunity_type"),
            description=rec.get("description"),
            naics_code=str(rec.get("naics_code") or ""),
            state=rec.get("state") or self.default_state,
            city=rec.get("city"),
            estimated_value=self._parse_float(rec.get("estimated_value")),
            posted_date=self._parse_date(rec.get("posted_date")),
            due_date=self._parse_date(rec.get("due_date")),
            contact_name=rec.get("contact_name"),
            contact_email=rec.get("contact_email"),
            contact_phone=rec.get("contact_phone"),
            source_url=detail_url,
            documents=documents,
            raw_data=rec,
        )
