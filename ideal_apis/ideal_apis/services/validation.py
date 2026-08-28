from __future__ import annotations

import re
from typing import Any

from ideal_apis.config import Settings
from ideal_apis.exceptions import MissingAPIKeyError
from ideal_apis.http import HTTPClient


class ValidationService:
    """Phone and email validation for lead hygiene."""

    def __init__(self, http: HTTPClient, settings: Settings):
        self.http = http
        self.settings = settings

    @staticmethod
    def _basic_phone_check(number: str) -> dict[str, Any]:
        digits = re.sub(r"\D", "", number)
        if len(digits) == 11 and digits.startswith("1"):
            digits = digits[1:]
        valid = len(digits) == 10 and digits[0] in "23456789"
        return {
            "valid": valid,
            "number": digits,
            "country_code": "US",
            "provider": "basic",
            "line_type": "unknown",
        }

    def validate_phone(self, number: str, *, provider: str = "auto") -> dict[str, Any]:
        if provider in ("auto", "numverify") and self.settings.numverify_key:
            return self.http.get(
                "http://apilayer.net/api/validate",
                service="Numverify",
                params={"access_key": self.settings.numverify_key, "number": number},
            )
        if provider in ("auto", "veriphone") and self.settings.veriphone_key:
            return self.http.get(
                "https://api.veriphone.io/v2/verify",
                service="Veriphone",
                params={"key": self.settings.veriphone_key, "phone": number},
            )
        if provider == "basic":
            return self._basic_phone_check(number)
        # Free fallback when no paid keys configured
        return self._basic_phone_check(number)

    def validate_email(self, email: str, *, provider: str = "auto") -> dict[str, Any]:
        if provider in ("auto", "kickbox") and self.settings.kickbox_key:
            return self.http.get(
                "https://api.kickbox.com/v2/verify",
                service="Kickbox",
                params={"email": email, "apikey": self.settings.kickbox_key},
            )
        # Free fallbacks (no API key)
        try:
            return self.http.get(
                "https://open.kickbox.com/v1/disposable/" + email,
                service="Kickbox Open",
            )
        except Exception:
            return self.http.get(
                "https://api.eva.pingutil.com/email",
                service="EVA Email",
                params={"email": email},
            )
