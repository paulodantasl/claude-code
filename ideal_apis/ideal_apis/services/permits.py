from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from ideal_apis.config import Settings
from ideal_apis.http import HTTPClient


class PermitsService:
    """Socrata open-data permits and dataset catalog search."""

    DATAGOV_V4 = "https://api.gsa.gov/technology/datagov/v4/search"
    SOCRATA_CATALOG = "https://api.us.socrata.com/api/catalog/v1"

    def __init__(self, http: HTTPClient, settings: Settings):
        self.http = http
        self.settings = settings

    def socrata_query(
        self,
        endpoint: str,
        *,
        where: str | None = None,
        select: str | None = None,
        order: str | None = None,
        limit: int = 1000,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        params: dict[str, Any] = {"$limit": limit, "$offset": offset}
        if where:
            params["$where"] = where
        if select:
            params["$select"] = select
        if order:
            params["$order"] = order
        headers = {"Accept": "application/json"}
        if self.settings.socrata_app_token:
            headers["X-App-Token"] = self.settings.socrata_app_token
        result = self.http.get(endpoint, service="Socrata", params=params, headers=headers)
        return result if isinstance(result, list) else [result]

    def recent_permits(
        self,
        endpoint: str,
        *,
        date_column: str = "issued_date",
        days_back: int = 7,
        extra_where: str | None = None,
        limit: int = 500,
    ) -> list[dict[str, Any]]:
        since = (datetime.now(timezone.utc) - timedelta(days=days_back)).strftime("%Y-%m-%dT00:00:00")
        where = f"{date_column} >= '{since}'"
        if extra_where:
            where = f"({where}) AND ({extra_where})"
        return self.socrata_query(
            endpoint,
            where=where,
            order=f"{date_column} DESC",
            limit=limit,
        )

    def datagov_search(self, query: str, *, limit: int = 20) -> dict[str, Any]:
        """Search dataset catalog — v4 API when keyed, else Socrata catalog (free)."""
        if self.settings.datagov_key:
            params = {"q": query, "per_page": limit}
            headers = {"X-Api-Key": self.settings.datagov_key}
            try:
                return self.http.get(
                    self.DATAGOV_V4,
                    service="Data.gov",
                    params=params,
                    headers=headers,
                )
            except Exception:
                pass
        return self.socrata_catalog_search(query, limit=limit)

    def socrata_catalog_search(self, query: str, *, limit: int = 20) -> dict[str, Any]:
        """Free fallback: search Socrata open-data catalog for permit datasets."""
        return self.http.get(
            self.SOCRATA_CATALOG,
            service="Socrata Catalog",
            params={"q": query, "only": "datasets", "limit": limit},
        )

    def find_florida_permit_datasets(self, county: str | None = None) -> dict[str, Any]:
        q = "building permits Florida"
        if county:
            q += f" {county}"
        return self.datagov_search(q, limit=25)
