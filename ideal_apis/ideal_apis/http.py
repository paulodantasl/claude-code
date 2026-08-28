from __future__ import annotations

from typing import Any

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from ideal_apis.config import Settings, get_settings
from ideal_apis.exceptions import APIRequestError


class HTTPClient:
    """Shared HTTP client with retries and consistent error handling."""

    def __init__(self, settings: Settings | None = None, timeout: float = 30.0):
        self.settings = settings or get_settings()
        self.timeout = timeout

    def _client(self) -> httpx.Client:
        return httpx.Client(
            timeout=self.timeout,
            headers={"User-Agent": self.settings.user_agent},
            follow_redirects=True,
        )

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=8))
    def request(
        self,
        method: str,
        url: str,
        *,
        service: str,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
        data: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> Any:
        with self._client() as client:
            response = client.request(
                method,
                url,
                params=params,
                json=json,
                data=data,
                headers=headers,
            )
        if response.status_code >= 400:
            detail = response.text[:500]
            raise APIRequestError(service, response.status_code, detail)
        if not response.content:
            return None
        content_type = response.headers.get("content-type", "")
        if "application/json" in content_type or response.text.startswith(("{", "[")):
            return response.json()
        return response.text

    def get(self, url: str, *, service: str, **kwargs: Any) -> Any:
        return self.request("GET", url, service=service, **kwargs)

    def post(self, url: str, *, service: str, **kwargs: Any) -> Any:
        return self.request("POST", url, service=service, **kwargs)
