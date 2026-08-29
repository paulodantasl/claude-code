"""
SAM.gov Opportunities source.

SAM.gov is the U.S. federal system for award management. Its public
"Get Opportunities" REST API returns contract opportunities (presolicitations,
solicitations, combined synopsis/solicitation, etc.) filtered by NAICS, date,
place of performance, and set-aside.

API docs: https://open.gsa.gov/api/get-opportunities-public-api/
Requires a free api.data.gov key (env: SAM_GOV_API_KEY).
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any

import requests
from tenacity import retry, stop_after_attempt, wait_exponential

from .base import BaseSource, RawDocument, RawOpportunity

logger = logging.getLogger(__name__)

ENDPOINT = "https://api.sam.gov/opportunities/v2/search"

# SAM.gov solicitation "type" codes → our normalised opportunity_type
TYPE_MAP = {
    "o": "IFB",   # Solicitation
    "p": "RFP",   # Presolicitation
    "k": "RFP",   # Combined Synopsis/Solicitation
    "r": "RFP",   # Sources Sought
    "g": "IFB",   # Sale of Surplus Property
}


class SamGovSource(BaseSource):
    """Pulls federal construction opportunities from the SAM.gov public API."""

    def __init__(self, source_config: dict[str, Any]):
        super().__init__(source_config)
        self.api_key = source_config.get("api_key")
        # Construction NAICS default to the 23* sector if none configured.
        self.naics_codes: list[str] = [str(n) for n in source_config.get("naics_codes", [])]
        self.states: list[str] = [s.upper() for s in source_config.get("states", [])]
        self.page_limit = int(source_config.get("page_limit", 1000))

    @retry(stop=stop_after_attempt(4), wait=wait_exponential(multiplier=2, min=2, max=30))
    def _fetch_page(self, params: dict) -> dict:
        resp = requests.get(ENDPOINT, params=params, timeout=45)
        resp.raise_for_status()
        return resp.json()

    def fetch(self, days_back: int = 7, keywords: list[str] | None = None) -> list[RawOpportunity]:
        if not self.api_key:
            self.logger.warning(
                "SAM_GOV_API_KEY not set — skipping SAM.gov source. "
                "Get a free key at https://api.data.gov/signup/"
            )
            return []

        posted_from = (datetime.utcnow() - timedelta(days=days_back)).strftime("%m/%d/%Y")
        posted_to = datetime.utcnow().strftime("%m/%d/%Y")

        results: list[RawOpportunity] = []
        # SAM.gov filters by a single NAICS per call; iterate configured codes.
        naics_iter = self.naics_codes or [None]

        for naics in naics_iter:
            offset = 0
            while True:
                params: dict[str, Any] = {
                    "api_key": self.api_key,
                    "postedFrom": posted_from,
                    "postedTo": posted_to,
                    "limit": 1000,
                    "offset": offset,
                    "ptype": "o,p,k",   # solicitation, presol, combined synopsis
                }
                if naics:
                    params["ncode"] = naics
                if self.states:
                    params["state"] = ",".join(self.states)
                if keywords:
                    params["title"] = " ".join(keywords)

                self.logger.info(
                    "SAM.gov fetch naics=%s offset=%d (days_back=%d)", naics, offset, days_back
                )
                try:
                    payload = self._fetch_page(params)
                except Exception as exc:
                    self.logger.error("SAM.gov page failed: %s", exc)
                    break

                rows = payload.get("opportunitiesData", []) or []
                for row in rows:
                    opp = self._normalise(row)
                    if opp:
                        results.append(opp)

                total = payload.get("totalRecords", 0)
                offset += 1000
                if offset >= total or not rows or offset >= self.page_limit:
                    break

        self.logger.info("SAM.gov returned %d opportunities", len(results))
        return results

    def _normalise(self, row: dict) -> RawOpportunity | None:
        notice_id = row.get("noticeId")
        if not notice_id:
            return None

        pop = (row.get("placeOfPerformance") or {})
        state = ((pop.get("state") or {}).get("code")) if isinstance(pop.get("state"), dict) else pop.get("state")
        city = ((pop.get("city") or {}).get("name")) if isinstance(pop.get("city"), dict) else pop.get("city")

        contact = (row.get("pointOfContact") or [{}])
        poc = contact[0] if contact else {}

        award = row.get("award") or {}
        est_value = self._parse_float(award.get("amount"))

        documents = [
            RawDocument(name=link.get("desc") or link.get("href", "document"), url=link["href"])
            for link in (row.get("resourceLinks") or [])
            if isinstance(link, dict) and link.get("href")
        ] if isinstance(row.get("resourceLinks"), list) else [
            RawDocument(name="Attachment", url=href)
            for href in (row.get("resourceLinks") or [])
            if isinstance(href, str)
        ]

        return RawOpportunity(
            source_id=str(notice_id),
            source=self.source_id,
            source_name=self.source_name,
            solicitation_number=row.get("solicitationNumber"),
            title=row.get("title"),
            agency=(row.get("fullParentPathName") or row.get("department")),
            opportunity_type=TYPE_MAP.get((row.get("type") or "").lower()[:1], row.get("type")),
            description=row.get("description"),
            naics_code=str(row.get("naicsCode") or ""),
            psc_code=str(row.get("classificationCode") or ""),
            set_aside=row.get("typeOfSetAsideDescription"),
            state=state,
            city=city,
            zip_code=pop.get("zip"),
            estimated_value=est_value,
            posted_date=self._parse_date(row.get("postedDate")),
            due_date=self._parse_date(row.get("responseDeadLine")),
            contact_name=poc.get("fullName"),
            contact_email=poc.get("email"),
            contact_phone=poc.get("phone"),
            source_url=row.get("uiLink"),
            documents=documents,
            raw_data=row,
        )
