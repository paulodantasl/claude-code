from __future__ import annotations

from typing import Any

from ideal_apis.config import Settings
from ideal_apis.exceptions import MissingAPIKeyError
from ideal_apis.http import HTTPClient


class LogisticsService:
    """Material delivery tracking."""

    def __init__(self, http: HTTPClient, settings: Settings):
        self.http = http
        self.settings = settings

    def whereparcel_track(self, tracking_number: str, *, carrier: str | None = None) -> dict[str, Any]:
        if not self.settings.whereparcel_key:
            raise MissingAPIKeyError("WhereParcel", "IDEAL_WHEREPARCEL_KEY")
        params: dict[str, Any] = {"tracking_number": tracking_number}
        if carrier:
            params["carrier"] = carrier
        return self.http.get(
            "https://api.whereparcel.com/v1/track",
            service="WhereParcel",
            params=params,
            headers={"Authorization": f"Bearer {self.settings.whereparcel_key}"},
        )

    def ups_track(self, tracking_number: str) -> dict[str, Any]:
        if not self.settings.ups_client_id or not self.settings.ups_client_secret:
            raise MissingAPIKeyError("UPS", "IDEAL_UPS_CLIENT_ID / IDEAL_UPS_CLIENT_SECRET")
        token = self.http.post(
            "https://onlinetools.ups.com/security/v1/oauth/token",
            service="UPS",
            data={"grant_type": "client_credentials"},
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "Authorization": (
                    f"Basic {self._ups_basic_auth()}"
                ),
            },
        )
        access_token = token["access_token"]
        return self.http.get(
            f"https://onlinetools.ups.com/api/track/v1/details/{tracking_number}",
            service="UPS",
            headers={
                "Authorization": f"Bearer {access_token}",
                "transId": tracking_number,
                "transactionSrc": "ideal-apis",
            },
        )

    def _ups_basic_auth(self) -> str:
        import base64

        raw = f"{self.settings.ups_client_id}:{self.settings.ups_client_secret}".encode()
        return base64.b64encode(raw).decode()
