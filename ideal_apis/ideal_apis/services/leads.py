from __future__ import annotations

from typing import Any

from ideal_apis.config import Settings
from ideal_apis.exceptions import MissingAPIKeyError
from ideal_apis.http import HTTPClient

NPPES_BASE = "https://npiregistry.cms.hhs.gov/api/"
CMS_PROVIDER_BASE = "https://data.cms.gov/provider-data/api/1/datastore/query"


class LeadsService:
    """Healthcare and local-business lead discovery."""

    def __init__(self, http: HTTPClient, settings: Settings):
        self.http = http
        self.settings = settings

    def nppes_search(
        self,
        *,
        state: str | None = None,
        city: str | None = None,
        taxonomy_description: str | None = None,
        organization_name: str | None = None,
        first_name: str | None = None,
        last_name: str | None = None,
        postal_code: str | None = None,
        limit: int = 50,
        skip: int = 0,
        enumeration_type: str | None = "NPI-2",
    ) -> dict[str, Any]:
        params: dict[str, Any] = {"version": "2.1", "limit": min(limit, 200), "skip": skip}
        if state:
            params["state"] = state
        if city:
            params["city"] = city
        if taxonomy_description:
            params["taxonomy_description"] = taxonomy_description
        if organization_name:
            params["organization_name"] = organization_name
        if first_name:
            params["first_name"] = first_name
        if last_name:
            params["last_name"] = last_name
        if postal_code:
            params["postal_code"] = postal_code
        if enumeration_type:
            params["enumeration_type"] = enumeration_type
        return self.http.get(NPPES_BASE, service="NPPES", params=params)

    def dentists_tampa_bay(self, limit: int = 50) -> dict[str, Any]:
        """Convenience: new dental org leads in FL Tampa Bay counties."""
        return self.nppes_search(
            state="FL",
            taxonomy_description="Dentist",
            limit=limit,
            enumeration_type="NPI-2",
        )

    def yelp_search(
        self,
        term: str,
        location: str,
        *,
        categories: str | None = None,
        limit: int = 20,
    ) -> dict[str, Any]:
        if not self.settings.yelp_key:
            raise MissingAPIKeyError("Yelp", "IDEAL_YELP_KEY")
        params: dict[str, Any] = {"term": term, "location": location, "limit": limit}
        if categories:
            params["categories"] = categories
        return self.http.get(
            "https://api.yelp.com/v3/businesses/search",
            service="Yelp",
            params=params,
            headers={"Authorization": f"Bearer {self.settings.yelp_key}"},
        )

    def cms_providers(
        self,
        dataset_id: str,
        *,
        filters: dict[str, Any] | None = None,
        limit: int = 25,
        offset: int = 0,
    ) -> dict[str, Any]:
        """Query a CMS provider dataset via data.cms.gov."""
        payload: dict[str, Any] = {
            "limit": limit,
            "offset": offset,
        }
        if filters:
            payload["conditions"] = filters
        headers = {}
        if self.settings.datagov_key:
            headers["X-Api-Key"] = self.settings.datagov_key
        return self.http.post(
            f"{CMS_PROVIDER_BASE}/{dataset_id}/0",
            service="CMS.gov",
            json=payload,
            headers=headers or None,
        )
