"""
Bid Radar collector — City of Tampa building permits.

Reads the public ArcGIS FeatureServer layer, keeps commercial records inside
the eight tracked submarkets, classifies them, and writes:

    bid_radar/data/signals.jsonl   one RawSignal per line
    bid_radar/data/summary.md      what a human reads on Monday morning

Runs in GitHub Actions; the Claude sandbox cannot reach the host (PLAN.md §0).

What this source can and cannot tell us — established from the layer itself on
2026-09-14, not assumed:

  * PROJECTSTATUS only ever reads `Issued` or `Revision`. There is no
    application or in-review stage, so a permit here is NOT advance notice of
    a job going out to bid. The exception is `EARLY START`, where the city has
    released interior non-structural work while the main permit is still
    pending — those have a live buyout window.
  * There is no valuation, applicant, owner or contractor field. Value cannot
    be scored from this source and the tenant has to be parsed out of
    PROJECTNAME2 / PROJECTDESCRIPTION.
  * CREATEDDATE is the intake date and LASTUPDATE the issue/update date; the
    gap ran 15-66 days (median 35) across the 25 most recent commercial
    records.
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone

import requests

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import classify  # noqa: E402
import geo  # noqa: E402

SERVICE = os.environ.get(
    "TAMPA_SERVICE",
    "https://arcgis.tampagov.net/arcgis/rest/services/Planning/PermitsAll/FeatureServer",
)
LAYER = int(os.environ.get("TAMPA_LAYER", "0"))
QUERY = f"{SERVICE}/{LAYER}/query"
DAYS_BACK = int(os.environ.get("DAYS_BACK", "90"))
PAGE = 1000
TIMEOUT = 60

DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
RETRIEVED_AT = datetime.now(timezone.utc).isoformat(timespec="seconds")

TRADE_ORDER = ["medical", "restaurant", "hospitality", "retail", "office", "other"]


def _ms_to_date(v) -> str | None:
    if not isinstance(v, (int, float)) or v <= 0:
        return None
    return datetime.fromtimestamp(v / 1000, timezone.utc).date().isoformat()


def fetch(where: str) -> list[dict]:
    """Page through the layer. Geometry is requested in WGS84."""
    out, offset = [], 0
    while True:
        resp = requests.get(QUERY, params={
            "where": where,
            "outFields": "*",
            "returnGeometry": "true",
            "outSR": 4326,
            "orderByFields": "CREATEDDATE DESC",
            "resultOffset": offset,
            "resultRecordCount": PAGE,
            "f": "json",
        }, timeout=TIMEOUT)
        resp.raise_for_status()
        body = resp.json()
        if "error" in body:
            raise RuntimeError(f"ArcGIS error: {body['error']}")
        feats = body.get("features", [])
        out.extend(feats)
        if not feats or not body.get("exceededTransferLimit"):
            return out
        offset += PAGE


def to_signal(feat: dict) -> dict | None:
    a = feat.get("attributes", {})
    g = feat.get("geometry") or {}
    lon, lat = g.get("x"), g.get("y")
    record_id = (a.get("RECORD_ID") or "").strip()
    if not record_id:
        return None

    name2 = (a.get("PROJECTNAME2") or "").strip()
    name1 = (a.get("PROJECTNAME1") or "").strip()
    desc = (a.get("PROJECTDESCRIPTION") or "").strip()
    occ = (a.get("OCCUPANCYCATEGORY") or "").strip()
    record_type = (a.get("RECORDTYPE") or "").strip()

    trade, confidence = classify.trade_of(occ, name2, desc)
    address = " ".join((a.get("ADDRESS") or "").split())
    unit = (a.get("UNIT") or "").strip()
    sqft = a.get("NEWCONSTRUCTIONSF") or None

    return {
        "id": "permit-" + hashlib.sha1(f"permit:{record_id}".encode()).hexdigest()[:16],
        "source": "permit",
        "source_id": record_id,
        "source_url": (a.get("URL") or "").strip() or None,
        "retrieved_at": RETRIEVED_AT,

        "hood": geo.hood_of(lon, lat),
        "address": f"{address} #{unit}" if unit else address,
        "zip": (a.get("ZIP") or "").strip() or None,
        "lat": lat, "lon": lon,
        "city_neighborhood": (a.get("NEIGHBORHOOD") or "").strip() or None,
        "cra": (a.get("CRA") or "").strip() or None,
        "council_district": (a.get("COUNCIL") or "").strip() or None,

        "entity": classify.entity_of(name2, desc),
        "brand": None,                    # Phase 1
        "trade": trade,
        "confidence": confidence,
        "stage_hint": classify.stage_of(a.get("PROJECTSTATUS"), name2, desc),
        "record_type": record_type,
        "occupancy_category": occ or None,
        "occupancy_type": (a.get("OCCUPANCYTYPE") or "").strip() or None,
        "is_fitout": classify.is_fitout(record_type),

        "value_est": None,                # field does not exist in this layer
        "sqft": sqft,
        "seats": None,
        "filed_at": _ms_to_date(a.get("CREATEDDATE")),
        "issued_at": _ms_to_date(a.get("LASTUPDATE")),
        "project_name": name2 or name1 or None,
        "description": desc or None,
        "private_provider": (a.get("PRIVATEPROVIDER") or "").strip() or None,
        "stop_work_order": (a.get("STOPWORKORDER") or "").strip() or None,
        "contacts": [],                   # no contact field in this source
    }


def summary(signals: list[dict], stats: dict) -> str:
    tracked = [s for s in signals if s["hood"]]
    fitouts = [s for s in tracked if s["is_fitout"]]
    early = [s for s in fitouts if s["stage_hint"] == "early_start"]

    L: list[str] = []
    L.append("# Tampa Bid Radar — permit signals")
    L.append("")
    L.append(f"Collected {RETRIEVED_AT} · window {DAYS_BACK} days by application "
             f"(CREATEDDATE) · source [City of Tampa PermitsAll]({SERVICE}/{LAYER})")
    L.append("")
    L.append(f"- {stats['fetched']} commercial records in the window")
    L.append(f"- **{len(tracked)}** inside a tracked submarket "
             f"({len(fitouts)} of them fitout-capable, {len(early)} at EARLY START)")
    L.append("")
    L.append("> This layer publishes permits at issuance — it has no application "
             "stage. A row below is a job that is already permitted unless it is "
             "tagged `early_start`, where the main permit is still pending and "
             "buyout is open. There is no valuation, applicant or contractor "
             "field in the source, so those columns are absent rather than "
             "guessed.")
    L.append("")

    L.append("## By submarket × trade (fitout-capable records)")
    L.append("")
    grid: dict[str, Counter] = defaultdict(Counter)
    for s in fitouts:
        grid[s["hood"]][s["trade"]] += 1
    trades = [t for t in TRADE_ORDER if any(g[t] for g in grid.values())]
    if trades:
        L.append("| Submarket | " + " | ".join(trades) + " | total |")
        L.append("|---|" + "---|" * (len(trades) + 1))
        for hood in geo.all_hoods():
            row = grid.get(hood)
            if not row:
                continue
            L.append(f"| {geo.hood_label(hood)} | "
                     + " | ".join(str(row[t] or "") for t in trades)
                     + f" | **{sum(row.values())}** |")
    else:
        L.append("_No fitout-capable records inside a tracked submarket in this window._")
    L.append("")

    if early:
        L.append("## EARLY START — main permit still pending, buyout open")
        L.append("")
        L.append(_table(early))
        L.append("")

    L.append("## All fitout-capable records in tracked submarkets")
    L.append("")
    L.append(_table(sorted(fitouts, key=lambda s: (s["filed_at"] or ""), reverse=True))
             if fitouts else "_none in this window_")
    L.append("")

    other = [s for s in tracked if not s["is_fitout"]]
    if other:
        L.append("## Commercial demolition in tracked submarkets (precursor signal)")
        L.append("")
        L.append(_table(other))
        L.append("")

    L.append("## Source notes")
    L.append("")
    L.append(f"- Layer total: {stats.get('layer_total', 'n/a')} features; "
             f"record types present: {', '.join(sorted(stats['record_types']))}")
    L.append(f"- Commercial records outside every tracked submarket: "
             f"{stats['fetched'] - len(tracked)}")
    L.append("- `source_url` is the City of Tampa Accela record page for that permit.")
    return "\n".join(L)


def _table(rows: list[dict]) -> str:
    head = ("| Permit | Filed | Stage | Submarket | Trade | Tenant / project | "
            "Address | Source |")
    out = [head, "|---|---|---|---|---|---|---|---|"]
    for s in rows:
        name = (s["entity"] or s["project_name"] or "—").replace("|", "/")
        if len(name) > 60:
            name = name[:57] + "…"
        link = f"[record]({s['source_url']})" if s["source_url"] else "—"
        out.append(
            f"| `{s['source_id']}` | {s['filed_at'] or '—'} | {s['stage_hint']} | "
            f"{geo.hood_label(s['hood'])} | {s['trade']} | {name} | "
            f"{s['address'] or '—'} | {link} |")
    return "\n".join(out)


def main() -> int:
    since = (datetime.now(timezone.utc) - timedelta(days=DAYS_BACK)).strftime("%Y-%m-%d")
    types = "','".join(sorted(classify.COMMERCIAL_RECORD_TYPES))
    where = f"CREATEDDATE >= DATE '{since}' AND RECORDTYPE IN ('{types}')"
    print(f"WHERE {where}", flush=True)

    feats = fetch(where)
    print(f"fetched {len(feats)} features", flush=True)

    signals = [s for s in (to_signal(f) for f in feats) if s]
    signals.sort(key=lambda s: (s["filed_at"] or ""), reverse=True)

    try:
        total = requests.get(QUERY, params={"where": "1=1", "returnCountOnly": "true",
                                            "f": "json"}, timeout=TIMEOUT).json().get("count")
    except Exception:  # noqa: BLE001
        total = None

    stats = {
        "fetched": len(signals),
        "layer_total": total,
        "record_types": {s["record_type"] for s in signals if s["record_type"]},
    }

    os.makedirs(DATA, exist_ok=True)
    with open(os.path.join(DATA, "signals.jsonl"), "w") as fh:
        for s in signals:
            fh.write(json.dumps(s, separators=(",", ":")) + "\n")
    with open(os.path.join(DATA, "summary.md"), "w") as fh:
        fh.write(summary(signals, stats) + "\n")

    tracked = [s for s in signals if s["hood"]]
    print(f"wrote {len(signals)} signals, {len(tracked)} in a tracked submarket", flush=True)
    for hood, n in Counter(s["hood"] for s in tracked).most_common():
        print(f"  {hood:<12} {n}", flush=True)
    if not tracked:
        print("WARNING: no signal landed in a tracked submarket — check the "
              "polygons or widen DAYS_BACK", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
