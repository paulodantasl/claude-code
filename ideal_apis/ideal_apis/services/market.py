from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from ideal_apis.config import Settings
from ideal_apis.exceptions import MissingAPIKeyError
from ideal_apis.http import HTTPClient


class MarketService:
    """Material and labor cost movement from FRED, for escalation and bid validity.

    The point of this module is to turn "we think material is moving" into a cited
    number: pull the producer price index for the commodities that dominate a bid,
    measure the move over the exposure window, and either carry an escalation
    allowance or shorten bid validity.
    """

    BASE = "https://api.stlouisfed.org/fred"

    #: Curated series relevant to a GC's cost exposure. Anything not listed here is
    #: discoverable with :meth:`search` — e.g. search("ready-mix concrete") or
    #: search("gypsum products") returns the PPI series for those commodities.
    SERIES: dict[str, str] = {
        "construction_materials": "WPUSI012011",  # PPI: inputs to construction industries
        "all_commodities": "PPIACO",
        "lumber_wood": "WPU081",
        "iron_steel": "WPU101",
        "total_construction_spending": "TTLCONS",
        "housing_starts": "HOUST",
        "construction_earnings": "CES2000000003",  # avg hourly earnings, construction
        "mortgage_30yr": "MORTGAGE30US",
        "treasury_10yr": "DGS10",
    }

    def __init__(self, http: HTTPClient, settings: Settings):
        self.http = http
        self.settings = settings

    def _key(self) -> str:
        if not self.settings.fred_key:
            raise MissingAPIKeyError("FRED", "IDEAL_FRED_KEY")
        return self.settings.fred_key

    def _resolve(self, series: str) -> str:
        """Accept either a friendly name from SERIES or a raw FRED series id."""
        return self.SERIES.get(series, series)

    def observations(
        self,
        series: str,
        *,
        start_date: str | None = None,
        end_date: str | None = None,
        limit: int | None = None,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {
            "series_id": self._resolve(series),
            "api_key": self._key(),
            "file_type": "json",
        }
        if start_date:
            params["observation_start"] = start_date
        if end_date:
            params["observation_end"] = end_date
        if limit:
            params["limit"] = limit
            params["sort_order"] = "desc"
        return self.http.get(f"{self.BASE}/series/observations", service="FRED", params=params)

    def search(self, text: str, *, limit: int = 20) -> dict[str, Any]:
        """Find a FRED series id by keyword — use this for commodities not in SERIES."""
        return self.http.get(
            f"{self.BASE}/series/search",
            service="FRED",
            params={
                "search_text": text,
                "api_key": self._key(),
                "file_type": "json",
                "limit": limit,
                "order_by": "popularity",
                "sort_order": "desc",
            },
        )

    def escalation(self, series: str = "construction_materials", *, months: int = 12) -> dict[str, Any]:
        """Percent change in a series over the trailing window.

        Returns the two endpoint observations plus the move between them, which is
        the number that belongs in an escalation clause or a bid-validity decision.
        """
        end = date.today()
        start = end - timedelta(days=int(months * 30.44) + 45)
        raw = self.observations(
            series,
            start_date=start.isoformat(),
            end_date=end.isoformat(),
        )
        points = [o for o in raw.get("observations", []) if o.get("value") not in (None, ".", "")]
        if len(points) < 2:
            return {
                "series": self._resolve(series),
                "months": months,
                "observations": len(points),
                "error": "not enough observations in window to measure a move",
            }
        first, last = points[0], points[-1]
        first_v, last_v = float(first["value"]), float(last["value"])
        pct = ((last_v - first_v) / first_v * 100) if first_v else 0.0
        annualized = None
        span_months = max((months if len(points) > 1 else 0), 1)
        if first_v:
            annualized = pct * (12 / span_months)
        return {
            "series": self._resolve(series),
            "series_name": series if series in self.SERIES else None,
            "months": months,
            "observations": len(points),
            "start": {"date": first["date"], "value": first_v},
            "end": {"date": last["date"], "value": last_v},
            "pct_change": round(pct, 2),
            "annualized_pct": round(annualized, 2) if annualized is not None else None,
        }

    def bid_exposure(self, *, months: int = 12) -> dict[str, Any]:
        """Escalation across every curated cost series, for a pre-bid read.

        One failing series (a retired id, a key without access) does not sink the
        rest — it comes back with its error recorded alongside the others.
        """
        report: dict[str, Any] = {"months": months, "series": {}}
        for name in self.SERIES:
            try:
                report["series"][name] = self.escalation(name, months=months)
            except Exception as exc:  # keep the rest of the read usable
                report["series"][name] = {"series": self.SERIES[name], "error": str(exc)}
        return report
