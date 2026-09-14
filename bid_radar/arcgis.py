"""
Shared ArcGIS FeatureServer access for every Tampa layer we read.

All four layers (PLAN.md §3) live on the same host, are public, serve point
geometry and page the same way, so this is the one place that talks HTTP.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Iterator
from urllib.parse import urlencode

import requests

HOST = "https://arcgis.tampagov.net/arcgis/rest/services"
TIMEOUT = 60
PAGE = 1000

# The alcoholic-beverage layer contains a date of 2997-01-29 and one of
# 0201-04-11. Anything outside this range is a data-entry error, not a date.
MIN_YEAR, MAX_YEAR = 1900, 2100


class ArcGISError(RuntimeError):
    pass


def query_url(service: str, layer: int = 0, kind: str = "FeatureServer") -> str:
    return f"{HOST}/{service}/{kind}/{layer}/query"


def record_url(service: str, layer: int, objectid: Any,
               kind: str = "FeatureServer") -> str:
    """A resolvable URL for one record, for layers with no link field of their
    own. It returns exactly the row the signal was built from."""
    params = urlencode({"where": f"OBJECTID={objectid}", "outFields": "*", "f": "json"})
    return f"{query_url(service, layer, kind)}?{params}"


def _get(url: str, params: dict) -> dict:
    resp = requests.get(url, params=params, timeout=TIMEOUT)
    resp.raise_for_status()
    body = resp.json()
    if "error" in body:
        raise ArcGISError(f"{url}: {body['error']}")
    return body


def fetch(service: str, layer: int = 0, *, where: str = "1=1",
          order_by: str | None = None, kind: str = "FeatureServer",
          geometry: bool = True) -> list[dict]:
    """Every feature matching `where`, paged, geometry in WGS84."""
    url = query_url(service, layer, kind)
    out: list[dict] = []
    offset = 0
    while True:
        params = {
            "where": where, "outFields": "*",
            "returnGeometry": "true" if geometry else "false",
            "outSR": 4326, "resultOffset": offset, "resultRecordCount": PAGE,
            "f": "json",
        }
        if order_by:
            params["orderByFields"] = order_by
        body = _get(url, params)
        feats = body.get("features", [])
        out.extend(feats)
        if not feats or not body.get("exceededTransferLimit"):
            return out
        offset += PAGE


def count(service: str, layer: int = 0, *, where: str = "1=1",
          kind: str = "FeatureServer") -> int | None:
    try:
        return _get(query_url(service, layer, kind),
                    {"where": where, "returnCountOnly": "true", "f": "json"}).get("count")
    except Exception:  # noqa: BLE001
        return None


def epoch_to_date(value: Any) -> str | None:
    """ArcGIS epoch-ms to an ISO date, or None when the value is not a date.

    Out-of-range values are dropped rather than carried: a lease signed in
    2997 would sort to the top of every list.
    """
    if not isinstance(value, (int, float)) or value == 0:
        return None
    try:
        dt = datetime.fromtimestamp(value / 1000, timezone.utc)
    except (OverflowError, OSError, ValueError):
        return None
    if not (MIN_YEAR <= dt.year <= MAX_YEAR):
        return None
    return dt.date().isoformat()


def us_date_to_iso(value: Any) -> str | None:
    """'08/20/2026' -> '2026-08-20'. Returns None for anything else."""
    if not isinstance(value, str) or not value.strip():
        return None
    for fmt in ("%m/%d/%Y", "%Y-%m-%d", "%m/%d/%y"):
        try:
            d = datetime.strptime(value.strip(), fmt).date()
        except ValueError:
            continue
        return d.isoformat() if MIN_YEAR <= d.year <= MAX_YEAR else None
    return None


def clean(value: Any) -> str | None:
    """Trim a string field; '' and whitespace become None."""
    if value is None:
        return None
    text = " ".join(str(value).split())
    return text or None


def number(value: Any) -> float | None:
    """Parse a numeric field that the source may have typed as a string.

    The alcoholic-beverage layer stores square footage as text and writes
    'See Ordinance' where it does not know, so this has to fail quietly.
    """
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value) or None
    try:
        return float(str(value).replace(",", "").replace("$", "").strip()) or None
    except ValueError:
        return None


def iter_attrs(features: list[dict]) -> Iterator[tuple[dict, float | None, float | None]]:
    for feat in features:
        geom = feat.get("geometry") or {}
        yield feat.get("attributes", {}), geom.get("x"), geom.get("y")


def dumps(obj: Any) -> str:
    return json.dumps(obj, separators=(",", ":"), default=str)
