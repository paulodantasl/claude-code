"""
Socrata Open Data API scraper.

Many cities/counties publish permits via Socrata (data.cityofXYZ.gov).
This adapter handles SoQL queries with date filtering and pagination.

Docs: https://dev.socrata.com/docs/queries/
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta
from typing import Any
from urllib.parse import urlencode

import requests
from tenacity import retry, stop_after_attempt, wait_exponential

from .base import BaseScraper, RawPermit

logger = logging.getLogger(__name__)

# Field name mappings per dataset (some counties use different column names)
FIELD_MAP_DEFAULTS = {
    "permit_number": ["permit_num", "permitnum", "permit_number", "record_id", "application_number"],
    "permit_type": ["permit_type", "permittype", "work_type", "job_type", "permit_category"],
    "status": ["status", "permit_status", "current_status"],
    "description": ["description", "work_description", "job_description", "scope_of_work"],
    "applicant_name": ["applicant_name", "applicant", "owner_name", "owner"],
    "contractor_name": ["contractor_name", "contractor", "contractor_business_name"],
    "address": ["address", "site_address", "full_address", "location_address", "job_location"],
    "city": ["city", "municipality", "jurisdiction"],
    "zip_code": ["zip", "zip_code", "zipcode", "postal_code"],
    "estimated_value": ["estimated_value", "job_value", "project_value", "declared_valuation", "value"],
    "filed_date": ["filed_date", "application_date", "applied_date", "date_filed", "issue_date"],
    "latitude": ["latitude", "lat", "y_coordinate"],
    "longitude": ["longitude", "lon", "long", "x_coordinate"],
}


def _find_field(record: dict, candidates: list[str]) -> Any:
    for key in candidates:
        for k in (key, key.upper(), key.lower()):
            if k in record:
                return record[k]
    return None


class SocrataPermitScraper(BaseScraper):
    """Fetches permits from a Socrata-powered open data portal."""

    def __init__(self, county_config: dict[str, Any]):
        super().__init__(county_config)
        self.endpoint = county_config["open_data_url"]
        self.app_token = county_config.get("socrata_app_token")   # optional but raises rate limit
        self.date_column = county_config.get("date_column", "filed_date")
        self.field_map: dict[str, list[str]] = {
            **FIELD_MAP_DEFAULTS,
            **county_config.get("field_map", {}),
        }

    @retry(stop=stop_after_attempt(4), wait=wait_exponential(multiplier=2, min=2, max=30))
    def _fetch_page(self, params: dict) -> list[dict]:
        headers = {"Accept": "application/json"}
        if self.app_token:
            headers["X-App-Token"] = self.app_token

        resp = requests.get(self.endpoint, params=params, headers=headers, timeout=30)
        resp.raise_for_status()
        return resp.json()

    def scrape(self, days_back: int = 7, permit_types: list[str] | None = None) -> list[RawPermit]:
        since = (datetime.utcnow() - timedelta(days=days_back)).strftime("%Y-%m-%dT00:00:00")
        date_col = self._detect_date_column()

        where_clauses = [f"{date_col} >= '{since}'"]
        if permit_types:
            type_conditions = " OR ".join(
                f"upper(permit_type) like '%{pt.upper()}%'" for pt in permit_types
            )
            where_clauses.append(f"({type_conditions})")

        limit = 1000
        offset = 0
        all_records: list[RawPermit] = []

        while True:
            params = {
                "$where": " AND ".join(where_clauses),
                "$order": f"{date_col} DESC",
                "$limit": limit,
                "$offset": offset,
            }
            self.logger.info(
                "Fetching %s offset=%d (days_back=%d)", self.county_name, offset, days_back
            )
            try:
                rows = self._fetch_page(params)
            except Exception as exc:
                self.logger.error("Failed to fetch page: %s", exc)
                break

            if not rows:
                break

            for row in rows:
                permit = self._normalise(row)
                if permit:
                    all_records.append(permit)

            if len(rows) < limit:
                break
            offset += limit

        self.logger.info("Fetched %d permits from %s", len(all_records), self.county_name)
        return all_records

    def _detect_date_column(self) -> str:
        """Try common date column names; fall back to config."""
        candidates = self.field_map.get("filed_date", []) + ["filed_date", "application_date", "date_filed"]
        # Trust config first
        return self.config.get("date_column") or candidates[0]

    def _normalise(self, row: dict) -> RawPermit | None:
        source_id = (
            _find_field(row, ["permit_num", "permitnum", "record_id", "application_number", "objectid"])
            or str(row)[:64]
        )
        if not source_id:
            return None

        # Flatten nested location if present (Socrata GeoJSON)
        if "location" in row and isinstance(row["location"], dict):
            coords = row["location"].get("coordinates", [])
            if len(coords) == 2:
                row.setdefault("longitude", coords[0])
                row.setdefault("latitude", coords[1])

        return RawPermit(
            source_id=str(source_id),
            county_id=self.county_id,
            county_name=self.county_name,
            permit_number=str(_find_field(row, self.field_map["permit_number"]) or ""),
            permit_type=str(_find_field(row, self.field_map["permit_type"]) or ""),
            status=str(_find_field(row, self.field_map["status"]) or ""),
            description=str(_find_field(row, self.field_map["description"]) or ""),
            applicant_name=str(_find_field(row, self.field_map["applicant_name"]) or ""),
            contractor_name=str(_find_field(row, self.field_map["contractor_name"]) or ""),
            address=str(_find_field(row, self.field_map["address"]) or ""),
            city=str(_find_field(row, self.field_map["city"]) or self.county_name),
            state=self.config.get("state"),
            zip_code=str(_find_field(row, self.field_map["zip_code"]) or ""),
            estimated_value=self._parse_float(_find_field(row, self.field_map["estimated_value"])),
            filed_date=self._parse_date(_find_field(row, self.field_map["filed_date"])),
            latitude=self._parse_float(_find_field(row, self.field_map["latitude"])),
            longitude=self._parse_float(_find_field(row, self.field_map["longitude"])),
            source_url=self.endpoint,
            raw_data=row,
        )
