"""
Generic RSS / Atom procurement-feed source.

Many state and local procurement portals publish open solicitations as an
RSS or Atom feed (e.g. Florida Vendor Bid System, several BidNet/DemandStar
agency feeds, OpenGov Procurement). This adapter parses those feeds into
normalised opportunities — no API key or browser required.

Configure per-feed in sources.yaml:

    - id: fl_vbs
      name: "Florida Vendor Bid System"
      type: rss
      feed_url: "https://www.myflorida.com/apps/vbs/vbs_www.rss"
      state: FL
      opportunity_type: ITB
"""
from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta
from email.utils import parsedate_to_datetime
from typing import Any

import requests
from tenacity import retry, stop_after_attempt, wait_exponential

try:
    import feedparser  # type: ignore
except ImportError:  # pragma: no cover - optional dependency
    feedparser = None

from .base import BaseSource, RawDocument, RawOpportunity

logger = logging.getLogger(__name__)

_VALUE_RE = re.compile(r"\$\s?([\d,]+(?:\.\d+)?)")
_SOL_RE = re.compile(r"\b([A-Z]{2,}[-\s]?\d{2,}[-\w/-]*)\b")


class RssSource(BaseSource):
    """Parses an RSS/Atom procurement feed into RawOpportunity records."""

    def __init__(self, source_config: dict[str, Any]):
        super().__init__(source_config)
        self.feed_url = source_config["feed_url"]
        self.default_state = source_config.get("state")
        self.default_type = source_config.get("opportunity_type")

    @retry(stop=stop_after_attempt(4), wait=wait_exponential(multiplier=2, min=2, max=30))
    def _fetch_raw(self) -> str:
        resp = requests.get(self.feed_url, timeout=30, headers={"User-Agent": "bid-tracker/0.1"})
        resp.raise_for_status()
        return resp.text

    def fetch(self, days_back: int = 7, keywords: list[str] | None = None) -> list[RawOpportunity]:
        if feedparser is None:
            self.logger.error("feedparser not installed — run `pip install feedparser`")
            return []

        try:
            raw = self._fetch_raw()
        except Exception as exc:
            self.logger.error("Feed fetch failed for %s: %s", self.feed_url, exc)
            return []

        parsed = feedparser.parse(raw)
        cutoff = datetime.utcnow() - timedelta(days=days_back)
        results: list[RawOpportunity] = []

        for entry in parsed.entries:
            posted = self._entry_date(entry)
            if posted and posted < cutoff:
                continue

            title = entry.get("title", "") or ""
            summary = entry.get("summary", "") or entry.get("description", "") or ""
            if keywords and not any(kw.lower() in f"{title} {summary}".lower() for kw in keywords):
                continue

            results.append(self._normalise(entry, posted, title, summary))

        self.logger.info("RSS %s returned %d opportunities", self.source_name, len(results))
        return results

    def _entry_date(self, entry: dict) -> datetime | None:
        for key in ("published", "updated", "pubDate"):
            val = entry.get(key)
            if val:
                try:
                    return parsedate_to_datetime(val).replace(tzinfo=None)
                except (TypeError, ValueError):
                    parsed = self._parse_date(val)
                    if parsed:
                        return parsed
        return None

    def _normalise(self, entry: dict, posted: datetime | None, title: str, summary: str) -> RawOpportunity:
        link = entry.get("link") or ""
        sol_match = _SOL_RE.search(title) or _SOL_RE.search(summary)
        val_match = _VALUE_RE.search(summary)
        documents = [
            RawDocument(name=enc.get("title", "Attachment"), url=enc["href"])
            for enc in entry.get("links", [])
            if isinstance(enc, dict) and enc.get("rel") == "enclosure" and enc.get("href")
        ]

        return RawOpportunity(
            source_id=entry.get("id") or link or title,
            source=self.source_id,
            source_name=self.source_name,
            solicitation_number=sol_match.group(1) if sol_match else None,
            title=title,
            agency=entry.get("author") or self.source_name,
            opportunity_type=self.default_type,
            description=re.sub(r"<[^>]+>", " ", summary).strip(),
            state=self.default_state,
            estimated_value=self._parse_float(val_match.group(1)) if val_match else None,
            posted_date=posted,
            source_url=link,
            documents=documents,
            raw_data=dict(entry),
        )
