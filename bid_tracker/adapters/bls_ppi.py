"""BLS Producer Price Index adapter -> cost_index.csv import package.

One POST covers every configured series. v2 (with BLS_API_KEY) allows more queries per day and
20-year spans; v1 works without a key. Annual averages (M13) are dropped; values footnoted "P"
are marked preliminary. A configured series BLS does not return is a hard error, so a typo in
sources.toml can't silently fall back to the wrong index.
"""

from __future__ import annotations

import os
from datetime import date
from pathlib import Path

from bid_tracker.adapters.http import Fetch, post_json, urllib_fetch
from bid_tracker.canonical import SPECS, write_csv
from bid_tracker.db import load_sources

SOURCE_PAGE = "https://data.bls.gov/timeseries/{series}"


class BLSError(RuntimeError):
    pass


def parse_bls(payload: dict, retrieved_at: str) -> list[dict]:
    if payload.get("status") != "REQUEST_SUCCEEDED":
        raise BLSError(f"BLS request failed: {payload.get('status')} {payload.get('message')}")
    rows = []
    for series in payload.get("Results", {}).get("series", []):
        sid = series["seriesID"]
        for d in series.get("data", []):
            period = d.get("period", "")
            if not period.startswith("M") or period == "M13":
                continue
            value = d.get("value", "").strip()
            if value in ("", "-"):
                continue
            prelim = any(f.get("code") == "P" for f in d.get("footnotes", []) if f)
            rows.append({
                "series_id": sid,
                "period": f"{d['year']}-{period[1:]}",
                "value": float(value),
                "preliminary": 1 if prelim else 0,
                "retrieved_at": retrieved_at,
                "source_url": SOURCE_PAGE.format(series=sid),
            })
    return rows


def fetch_series(series_ids: list[str], start_year: int, end_year: int, *, fetch: Fetch = urllib_fetch,
                 api_key: str | None = None) -> dict:
    cfg = load_sources()["bls"]
    payload = {"seriesid": series_ids, "startyear": str(start_year), "endyear": str(end_year)}
    url = cfg["endpoint_v1"]
    if api_key:
        payload["registrationkey"] = api_key
        url = cfg["endpoint_v2"]
    return post_json(url, payload, fetch=fetch)


def build_package(out_dir: Path, *, start_year: int | None = None, end_year: int | None = None,
                  fetch: Fetch = urllib_fetch, today: date | None = None) -> tuple[Path, int]:
    today = today or date.today()
    end_year = end_year or today.year
    # v1 caps a request at 10 years; v2 at 20.
    api_key = os.environ.get("BLS_API_KEY")
    start_year = start_year or end_year - (19 if api_key else 9)
    series = [s["series_id"] for s in load_sources().get("cost_index_series", [])]
    payload = fetch_series(series, start_year, end_year, fetch=fetch, api_key=api_key)
    rows = parse_bls(payload, today.isoformat())
    returned = {r["series_id"] for r in rows}
    missing = [s for s in series if s not in returned]
    if missing:
        raise BLSError(f"BLS returned no data for {', '.join(missing)}; fix the series id in sources.toml")
    write_csv(out_dir / "cost_index.csv", list(SPECS["cost_index.csv"]), rows)
    return out_dir, len(rows)
