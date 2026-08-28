from __future__ import annotations

from typing import Any

from ideal_apis.config import Settings
from ideal_apis.exceptions import MissingAPIKeyError
from ideal_apis.http import HTTPClient


class PropertyService:
    """Property research, corporate lookups, and school districts."""

    def __init__(self, http: HTTPClient, settings: Settings):
        self.http = http
        self.settings = settings

    def acrelens_score(self, lat: float, lon: float) -> dict[str, Any]:
        if not self.settings.acrelens_key:
            raise MissingAPIKeyError("AcreLens", "IDEAL_ACRELENS_KEY")
        return self.http.get(
            "https://api.acrelens.com/v1/score",
            service="AcreLens",
            params={"lat": lat, "lon": lon},
            headers={"X-API-Key": self.settings.acrelens_key},
        )

    def opencorporates_search(self, query: str, *, jurisdiction: str = "us_fl") -> dict[str, Any]:
        if not self.settings.opencorporates_key:
            raise MissingAPIKeyError("OpenCorporates", "IDEAL_OPENCORPORATES_KEY")
        return self.http.get(
            "https://api.opencorporates.com/v0.4/companies/search",
            service="OpenCorporates",
            params={"q": query, "jurisdiction_code": jurisdiction, "api_token": self.settings.opencorporates_key},
        )

    def district_by_address(self, address: str) -> dict[str, Any]:
        if not self.settings.districtapi_key:
            raise MissingAPIKeyError("DistrictAPI", "IDEAL_DISTRICTAPI_KEY")
        return self.http.get(
            "https://districtapi.dev/api/v1/districts",
            service="DistrictAPI",
            params={"address": address},
            headers={"X-API-Key": self.settings.districtapi_key},
        )
