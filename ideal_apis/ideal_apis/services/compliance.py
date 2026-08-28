from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from ideal_apis.config import Settings
from ideal_apis.http import HTTPClient


class ComplianceService:
    """Sub and vendor screening, and rule changes that move public-bid scope.

    On federally funded work we must not contract with an excluded party. Run a sub
    through :meth:`screen_vendor` at buyout and keep the response as the record.
    """

    OPENSANCTIONS = "https://api.opensanctions.org"
    FEDERAL_REGISTER = "https://www.federalregister.gov/api/v1"

    #: Rule topics worth watching on public work.
    WATCH_TERMS = [
        "Davis-Bacon",
        "prevailing wage",
        "Buy America",
        "construction safety",
    ]

    def __init__(self, http: HTTPClient, settings: Settings):
        self.http = http
        self.settings = settings

    def _os_headers(self) -> dict[str, str]:
        """OpenSanctions serves the open dataset without a key; a key raises limits."""
        if self.settings.opensanctions_key:
            return {"Authorization": f"ApiKey {self.settings.opensanctions_key}"}
        return {}

    def sanctions_search(
        self,
        query: str,
        *,
        dataset: str = "default",
        limit: int = 10,
    ) -> dict[str, Any]:
        return self.http.get(
            f"{self.OPENSANCTIONS}/search/{dataset}",
            service="OpenSanctions",
            params={"q": query, "limit": limit},
            headers=self._os_headers(),
        )

    def screen_vendor(self, name: str, *, threshold: float = 0.7) -> dict[str, Any]:
        """Screen one company or person and reduce it to a buyout decision.

        Returns a ``clear`` flag plus whatever crossed the score threshold, so the
        result can be filed against the sub without re-reading the raw payload.
        """
        raw = self.sanctions_search(name)
        results = raw.get("results", []) or []
        hits = [
            {
                "name": r.get("caption"),
                "score": r.get("score"),
                "schema": r.get("schema"),
                "datasets": r.get("datasets"),
                "topics": (r.get("properties") or {}).get("topics"),
            }
            for r in results
            if (r.get("score") or 0) >= threshold
        ]
        return {
            "query": name,
            "clear": not hits,
            "threshold": threshold,
            "hits": hits,
            "total_candidates": len(results),
        }

    def federal_register_search(
        self,
        term: str,
        *,
        days_back: int = 30,
        per_page: int = 20,
    ) -> dict[str, Any]:
        since = (date.today() - timedelta(days=days_back)).isoformat()
        return self.http.get(
            f"{self.FEDERAL_REGISTER}/documents.json",
            service="Federal Register",
            params={
                "conditions[term]": term,
                "conditions[publication_date][gte]": since,
                "per_page": per_page,
                "order": "newest",
                "fields[]": [
                    "title",
                    "publication_date",
                    "document_number",
                    "type",
                    "agencies",
                    "html_url",
                    "abstract",
                ],
            },
        )

    def rule_watch(self, *, days_back: int = 30) -> dict[str, Any]:
        """Sweep every watched topic — the standing check before a public bid goes out."""
        report: dict[str, Any] = {"days_back": days_back, "topics": {}}
        for term in self.WATCH_TERMS:
            try:
                found = self.federal_register_search(term, days_back=days_back, per_page=5)
                report["topics"][term] = {
                    "count": found.get("count", 0),
                    "documents": found.get("results", []),
                }
            except Exception as exc:
                report["topics"][term] = {"error": str(exc)}
        return report
