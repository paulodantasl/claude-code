from __future__ import annotations

from typing import Any

from ideal_apis.config import Settings
from ideal_apis.exceptions import MissingAPIKeyError
from ideal_apis.http import HTTPClient


class AddressService:
    """Smarty US address validation, autocomplete, and extraction."""

    BASE = "https://us-street.api.smarty.com/street-address"
    AUTOCOMPLETE = "https://us-autocomplete-pro.api.smarty.com/lookup"
    EXTRACT = "https://us-extract.api.smarty.com/"

    def __init__(self, http: HTTPClient, settings: Settings):
        self.http = http
        self.settings = settings

    def _auth(self) -> dict[str, str]:
        if not self.settings.smarty_auth_id or not self.settings.smarty_auth_token:
            raise MissingAPIKeyError("Smarty", "IDEAL_SMARTY_AUTH_ID / IDEAL_SMARTY_AUTH_TOKEN")
        return {
            "auth-id": self.settings.smarty_auth_id,
            "auth-token": self.settings.smarty_auth_token,
        }

    def validate(
        self,
        street: str,
        city: str,
        state: str,
        zipcode: str,
        *,
        match: str = "enhanced",
    ) -> list[dict[str, Any]]:
        params = {
            **self._auth(),
            "street": street,
            "city": city,
            "state": state,
            "zipcode": zipcode,
            "match": match,
            "candidates": 1,
        }
        return self.http.get(self.BASE, service="Smarty", params=params)

    def autocomplete(self, search: str, *, max_results: int = 5) -> dict[str, Any]:
        params = {**self._auth(), "search": search, "max_results": max_results}
        return self.http.get(self.AUTOCOMPLETE, service="Smarty", params=params)

    def extract_addresses(self, text: str, *, html: bool = False) -> dict[str, Any]:
        params = {**self._auth(), "html": str(html).lower()}
        return self.http.post(
            self.EXTRACT,
            service="Smarty",
            params=params,
            data={"text": text},
        )
