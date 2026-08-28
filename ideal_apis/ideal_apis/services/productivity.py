from __future__ import annotations

from typing import Any

from ideal_apis.config import Settings
from ideal_apis.exceptions import MissingAPIKeyError
from ideal_apis.http import HTTPClient


class ProductivityService:
    """Time tracking integrations."""

    def __init__(self, http: HTTPClient, settings: Settings):
        self.http = http
        self.settings = settings

    def clockify_workspaces(self) -> list[dict[str, Any]]:
        if not self.settings.clockify_key:
            raise MissingAPIKeyError("Clockify", "IDEAL_CLOCKIFY_KEY")
        result = self.http.get(
            "https://api.clockify.me/api/v1/workspaces",
            service="Clockify",
            headers={"X-Api-Key": self.settings.clockify_key},
        )
        return result if isinstance(result, list) else [result]

    def clockify_projects(self, workspace_id: str) -> list[dict[str, Any]]:
        if not self.settings.clockify_key:
            raise MissingAPIKeyError("Clockify", "IDEAL_CLOCKIFY_KEY")
        result = self.http.get(
            f"https://api.clockify.me/api/v1/workspaces/{workspace_id}/projects",
            service="Clockify",
            headers={"X-Api-Key": self.settings.clockify_key},
        )
        return result if isinstance(result, list) else [result]
