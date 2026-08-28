from __future__ import annotations

from typing import Any

from ideal_apis.config import Settings
from ideal_apis.exceptions import MissingAPIKeyError
from ideal_apis.http import HTTPClient


class GovernmentService:
    """Federal contracts, spending, compliance, and census data."""

    def __init__(self, http: HTTPClient, settings: Settings):
        self.http = http
        self.settings = settings

    def usaspending_search(
        self,
        *,
        keywords: list[str] | None = None,
        state: str | None = None,
        award_type_codes: list[str] | None = None,
        limit: int = 25,
    ) -> dict[str, Any]:
        filters: dict[str, Any] = {}
        if keywords:
            filters["keywords"] = keywords
        if state:
            filters["recipient_locations"] = [{"country": "USA", "state": state}]
        if award_type_codes:
            filters["award_type_codes"] = award_type_codes
        payload = {
            "filters": filters,
            "fields": [
                "Award ID",
                "Recipient Name",
                "Award Amount",
                "Awarding Agency",
                "Description",
                "Start Date",
                "End Date",
                "Place of Performance State Code",
            ],
            "limit": limit,
            "page": 1,
        }
        return self.http.post(
            "https://api.usaspending.gov/api/v2/search/spending_by_award/",
            service="USAspending",
            json=payload,
        )

    def usaspending_florida_construction(self, limit: int = 25) -> dict[str, Any]:
        return self.usaspending_search(
            keywords=["construction", "renovation", "buildout"],
            state="FL",
            award_type_codes=["A", "B", "C", "D"],
            limit=limit,
        )

    def federal_contracts(
        self,
        *,
        agency: str | None = None,
        state: str | None = None,
        limit: int = 25,
    ) -> dict[str, Any]:
        """Federal contract awards via USAspending (replaces deprecated onrender feed)."""
        filters: dict[str, Any] = {
            "award_type_codes": ["A", "B", "C", "D"],
        }
        if state:
            filters["recipient_locations"] = [{"country": "USA", "state": state}]
        if agency:
            filters["keywords"] = [agency]
        else:
            filters["keywords"] = ["construction"]
        payload = {
            "filters": filters,
            "fields": [
                "Award ID",
                "Recipient Name",
                "Award Amount",
                "Awarding Agency",
                "Description",
                "Start Date",
                "End Date",
                "Place of Performance State Code",
            ],
            "limit": limit,
            "page": 1,
        }
        return self.http.post(
            "https://api.usaspending.gov/api/v2/search/spending_by_award/",
            service="USAspending Contracts",
            json=payload,
        )

    def fastdol_lookup(self, company_name: str) -> dict[str, Any]:
        if not self.settings.fastdol_key:
            raise MissingAPIKeyError("FastDOL", "IDEAL_FASTDOL_KEY")
        return self.http.get(
            "https://api.fastdol.com/v1/enforcement/search",
            service="FastDOL",
            params={"q": company_name},
            headers={"X-API-Key": self.settings.fastdol_key},
        )

    def census_geocoder(self, address: str, *, benchmark: str = "Public_AR_Current") -> dict[str, Any]:
        params = {
            "address": address,
            "benchmark": benchmark,
            "format": "json",
        }
        if self.settings.census_key:
            params["key"] = self.settings.census_key
        return self.http.get(
            "https://geocoding.geo.census.gov/geocoder/locations/onelineaddress",
            service="Census.gov",
            params=params,
        )

    def epa_envirofacts(self, table: str, *, rows: int = 10, **filters: str) -> dict[str, Any]:
        """Query EPA Envirofacts REST (table names vary by program).

        Row limits belong in the path as ``rows/0:N``, not as a query param — otherwise
        EPA may stream the entire table (e.g. all FL facilities).
        """
        base = table.rstrip("/")
        if "/rows/" not in base and not base.endswith("/JSON"):
            end = max(rows - 1, 0)
            base = f"{base}/rows/0:{end}"
        path = base if base.endswith("/JSON") else f"{base}/JSON"
        params: dict[str, Any] = dict(filters)
        return self.http.get(
            f"https://data.epa.gov/efservice/{path}",
            service="EPA",
            params=params or None,
        )

    def openfema_disasters(
        self,
        *,
        states: list[str] | None = None,
        incident_types: list[str] | None = None,
        days_back: int = 90,
        limit: int = 50,
    ) -> dict[str, Any]:
        """Recent FEMA disaster declarations (OpenFEMA v2)."""
        from datetime import datetime, timedelta, timezone

        since = (datetime.now(timezone.utc) - timedelta(days=days_back)).strftime("%Y-%m-%d")
        filters: list[str] = [f"declarationDate ge '{since}'"]
        if states:
            state_filter = " or ".join(f"state eq '{s}'" for s in states)
            filters.append(f"({state_filter})")
        if incident_types:
            type_filter = " or ".join(f"incidentType eq '{t}'" for t in incident_types)
            filters.append(f"({type_filter})")
        odata_filter = " and ".join(filters)
        return self.http.get(
            "https://www.fema.gov/api/open/v2/DisasterDeclarationsSummaries",
            service="OpenFEMA",
            params={
                "$filter": odata_filter,
                "$orderby": "declarationDate desc",
                "$top": limit,
            },
        )

