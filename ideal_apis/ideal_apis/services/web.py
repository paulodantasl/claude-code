from __future__ import annotations

from typing import Any

from ideal_apis.http import HTTPClient


class WebService:
    """URL metadata extraction for lead and bid research."""

    def __init__(self, http: HTTPClient):
        self.http = http

    def microlink(self, url: str, *, meta: bool = True) -> dict[str, Any]:
        params: dict[str, Any] = {"url": url}
        if meta:
            params["meta"] = "true"
        return self.http.get("https://api.microlink.io", service="Microlink", params=params)
