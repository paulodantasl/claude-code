"""
OpenGov Procurement source.

Many of the Tampa Bay agencies (Tampa, Pinellas County, St. Petersburg,
Hernando, Citrus, Bradenton, Fort Myers, Zephyrhills, Plant City) run their
solicitations on OpenGov Procurement. Their public portals
(procurement.opengov.com/portal/<agency>) are single-page apps, so a plain HTML
fetch returns an empty shell — the reliable path is OpenGov's documented REST
API.

API:   https://api.procurement.opengov.com/gateway/datasets/v1/solicitations
Auth:  API key via the `x-api-key` header (your OpenGov account email is the
       username and the API key the password for Basic Auth; we use x-api-key).
       Set OPENGOV_API_KEY in the environment — never hard-code it.

No login/password is needed to TRACK open solicitations (they are public). The
API key is the supported way to read them programmatically; obtain one from your
OpenGov account (Settings → Developer/API) or by contacting OpenGov support.

NOTE: field names below are mapped defensively against several candidates. Verify
them against a live response the first time you run with a real key, and adjust
FIELD_CANDIDATES if a value comes back empty.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta
from typing import Any

import requests
from tenacity import retry, stop_after_attempt, wait_exponential

from .base import BROWSER_USER_AGENT, BaseSource, RawDocument, RawOpportunity

logger = logging.getLogger(__name__)

ENDPOINT = "https://api.procurement.opengov.com/gateway/datasets/v1/solicitations"

# Statuses that mean "open for bidding" — anything else is filtered out.
OPEN_STATUSES = {"released", "open", "active", "published", "posted"}

FIELD_CANDIDATES = {
    "title": ["title", "name", "projectTitle"],
    "solicitation_number": ["referenceNumber", "solicitationNumber", "projectId", "number"],
    "agency": ["agencyName", "entityName", "departmentName", "organizationName"],
    "type": ["type", "solicitationType", "projectType"],
    "description": ["description", "summary", "scope"],
    "status": ["status", "state", "projectStatus"],
    "naics": ["naicsCode", "naics", "commodityCode"],
    "posted_date": ["releaseDate", "postedDate", "publishDate", "openDate", "createdAt"],
    "due_date": ["dueDate", "proposalDeadline", "closeDate", "submissionDeadline", "responseDueDate"],
    "question_due_date": ["questionDeadline", "qnaDeadline", "questionsDueDate"],
    "contact_name": ["contactName", "primaryContactName", "ownerName"],
    "contact_email": ["contactEmail", "primaryContactEmail", "ownerEmail"],
    "url": ["publicUrl", "portalUrl", "url", "link"],
}


def _attr(record: dict, candidates: list[str]) -> Any:
    """Look up a value in a JSON:API record (top-level or under `attributes`)."""
    attrs = record.get("attributes", record) if isinstance(record, dict) else {}
    for key in candidates:
        for container in (attrs, record):
            if isinstance(container, dict) and container.get(key) not in (None, ""):
                return container[key]
    return None


class OpenGovSource(BaseSource):
    """Reads open solicitations from the OpenGov Procurement API."""

    def __init__(self, source_config: dict[str, Any]):
        super().__init__(source_config)
        self.api_key = source_config.get("api_key") or os.environ.get("OPENGOV_API_KEY")
        self.email = source_config.get("email") or os.environ.get("OPENGOV_EMAIL")
        self.agency_filter = source_config.get("agency")          # optional client-side filter
        self.page_size = int(source_config.get("page_size", 100))
        self.max_pages = int(source_config.get("max_pages", 50))
        self.default_state = source_config.get("state")

    @retry(stop=stop_after_attempt(4), wait=wait_exponential(multiplier=2, min=2, max=30))
    def _fetch_page(self, params: dict) -> dict:
        headers = {
            "x-api-key": self.api_key,
            "Accept": "application/json",
            "User-Agent": BROWSER_USER_AGENT,
        }
        resp = requests.get(ENDPOINT, params=params, headers=headers, timeout=45)
        resp.raise_for_status()
        return resp.json()

    def fetch(self, days_back: int = 7, keywords: list[str] | None = None) -> list[RawOpportunity]:
        if not self.api_key:
            self.logger.warning(
                "OPENGOV_API_KEY not set — skipping OpenGov source. Open solicitations are "
                "publicly viewable at procurement.opengov.com, but the API key is required to "
                "read them programmatically. Generate one in your OpenGov account."
            )
            return []

        cutoff = datetime.utcnow() - timedelta(days=days_back)
        results: list[RawOpportunity] = []

        for page in range(1, self.max_pages + 1):
            params = {"page[number]": page, "page[size]": self.page_size}
            try:
                payload = self._fetch_page(params)
            except Exception as exc:
                self.logger.error("OpenGov page %d failed: %s", page, exc)
                break

            rows = payload.get("data", payload if isinstance(payload, list) else [])
            if not rows:
                break

            for row in rows:
                opp = self._normalise(row)
                if not opp:
                    continue
                # Status + recency filters
                if opp.raw_data.get("_status_norm") not in OPEN_STATUSES:
                    continue
                if opp.posted_date and opp.posted_date < cutoff:
                    continue
                if self.agency_filter and self.agency_filter.lower() not in (opp.agency or "").lower():
                    continue
                results.append(opp)

            # JSON:API pagination: stop when no "next" link
            links = payload.get("links", {}) if isinstance(payload, dict) else {}
            if not links.get("next"):
                if len(rows) < self.page_size:
                    break

        self.logger.info("OpenGov returned %d open opportunities", len(results))
        return results

    def _normalise(self, row: dict) -> RawOpportunity | None:
        rec_id = row.get("id") or _attr(row, ["id", "solicitationId"])
        if not rec_id:
            return None

        status_raw = str(_attr(row, FIELD_CANDIDATES["status"]) or "")
        documents = []
        for doc in (_attr(row, ["documents", "attachments", "files"]) or []):
            if isinstance(doc, dict) and (doc.get("url") or doc.get("href")):
                documents.append(RawDocument(name=doc.get("name", "Attachment"),
                                             url=doc.get("url") or doc.get("href")))

        raw = dict(row)
        raw["_status_norm"] = status_raw.lower()

        return RawOpportunity(
            source_id=str(rec_id),
            source=self.source_id,
            source_name=self.source_name,
            solicitation_number=_attr(row, FIELD_CANDIDATES["solicitation_number"]),
            title=_attr(row, FIELD_CANDIDATES["title"]),
            agency=_attr(row, FIELD_CANDIDATES["agency"]) or self.source_name,
            opportunity_type=_attr(row, FIELD_CANDIDATES["type"]),
            description=_attr(row, FIELD_CANDIDATES["description"]),
            naics_code=str(_attr(row, FIELD_CANDIDATES["naics"]) or ""),
            state=self.default_state,
            posted_date=self._parse_date(_attr(row, FIELD_CANDIDATES["posted_date"])),
            due_date=self._parse_date(_attr(row, FIELD_CANDIDATES["due_date"])),
            question_due_date=self._parse_date(_attr(row, FIELD_CANDIDATES["question_due_date"])),
            contact_name=_attr(row, FIELD_CANDIDATES["contact_name"]),
            contact_email=_attr(row, FIELD_CANDIDATES["contact_email"]),
            source_url=_attr(row, FIELD_CANDIDATES["url"]),
            documents=documents,
            raw_data=raw,
        )
