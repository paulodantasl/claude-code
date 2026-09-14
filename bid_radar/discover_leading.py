"""
DISCOVER round 3 — the two leading-indicator layers round 2 turned up.

PLAN.md §3 planned to reach alcoholic-beverage licences through the DBPR daily
CSV (source #3) and had no rezoning/site-plan source at all. Tampa publishes
both itself, on the same host and with no auth:

  Planning/AlcoholBeverage           4,096 features. Carries BUS_NAME,
                                     BUS_OWNER_NAME, BUS_PHONE, BUS_OWN_PHONE,
                                     BUS_OWN_EMAIL, SEAT_COUNT and
                                     AB_SLS_AREA_*_SF — i.e. an entity WITH a
                                     public contact channel, which the permit
                                     layer cannot give us.
  Planning/ActiveEntitlementLocations  289 features with APPSTATUS
                                     ("In Process") and TENTATIVEHEARING —
                                     the 9-18 month signal.
  Planning/CRACommercialInitiative    38 CRA grants with APPLICANT and
                                     AWARDEDAMOUNT — funded interior work.

This establishes, for each: which date field tracks a NEW application, the
status vocabulary, how populated the contact fields actually are, and whether
the geometry is point.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone

import requests

ROOT = "https://arcgis.tampagov.net/arcgis/rest/services/Planning"
TIMEOUT = 60
OUT: dict = {"retrieved_at": datetime.now(timezone.utc).isoformat()}

TARGETS = [
    ("abt", f"{ROOT}/AlcoholBeverage/FeatureServer/0",
     ["HISTORY_ACTION", "AB_CLASS_PREFIX", "AB_CLASS_SUFFIX", "POSTED",
      "ABSALETYPE", "ABSALECONDITION", "REPORT_CLASS", "REVIEWED"],
     ["BUS_NAME", "BUS_OWNER_NAME", "BUS_PHONE", "BUS_OWN_PHONE", "BUS_OWN_EMAIL",
      "SEAT_COUNT", "AB_SLS_AREA_TTL_SF", "PERMIT_ADDR", "APP_NUM", "ORD_PERMIT"]),
    ("entitlement", f"{ROOT}/ActiveEntitlementLocations/FeatureServer/0",
     ["APPSTATUS", "RECORDALIAS", "MAPDOT", "CRA", "COUNCILDISTRICT"],
     ["RECORDID", "ADDRESS", "TENTATIVEHEARING", "NEIGHBORHOOD", "URL"]),
    ("cra_grant", f"{ROOT}/CRACommercialInitiative/MapServer/0",
     ["STATUS", "GRANTTYPE", "CRA", "OCCUPANCY"],
     ["APPLICANT", "BUSINESSPROPERTYOWNER", "ADDRESS", "AWARDEDAMOUNT",
      "TOTALPROJECTCOST", "DESCRIPTION", "FISCALYEAR"]),
]


def hr(t: str) -> None:
    print("\n" + "=" * 70 + f"\n{t}\n" + "=" * 70, flush=True)


def q(url: str, params: dict):
    try:
        r = requests.get(url, params=params, timeout=TIMEOUT)
        r.raise_for_status()
        b = r.json()
        if "error" in b:
            print(f"  !! {b['error']}", flush=True)
            return None
        return b
    except Exception as exc:  # noqa: BLE001
        print(f"  !! {type(exc).__name__}: {exc}", flush=True)
        return None


def d(v):
    try:
        return datetime.fromtimestamp(v / 1000, timezone.utc).date().isoformat()
    except Exception:  # noqa: BLE001
        return None


since = (datetime.now(timezone.utc) - timedelta(days=365)).strftime("%Y-%m-%d")

for key, url, vocab_fields, show_fields in TARGETS:
    hr(f"{key}  —  {url}")
    entry: dict = {"url": url}
    meta = q(url, {"f": "json"})
    if not meta:
        OUT[key] = {"url": url, "error": "unreachable"}
        continue
    fields = {f["name"]: f["type"] for f in meta.get("fields", [])}
    entry["geometryType"] = meta.get("geometryType")
    print(f"  geometryType={meta.get('geometryType')}", flush=True)

    qurl = f"{url}/query"
    n = q(qurl, {"where": "1=1", "returnCountOnly": "true", "f": "json"})
    entry["count"] = (n or {}).get("count")
    print(f"  count={entry['count']}", flush=True)

    # Which date field moves? That is the one a new application lands on.
    entry["dates"] = {}
    for name, ftype in fields.items():
        if ftype != "esriFieldTypeDate":
            continue
        st = q(qurl, {"where": "1=1", "outStatistics": json.dumps([
            {"statisticType": "min", "onStatisticField": name, "outStatisticFieldName": "mn"},
            {"statisticType": "max", "onStatisticField": name, "outStatisticFieldName": "mx"},
            {"statisticType": "count", "onStatisticField": name, "outStatisticFieldName": "n"},
        ]), "f": "json"})
        row = (st or {}).get("features", [{}])[0].get("attributes", {})
        recent = q(qurl, {"where": f"{name} >= DATE '{since}'",
                          "returnCountOnly": "true", "f": "json"})
        entry["dates"][name] = {"min": d(row.get("mn")), "max": d(row.get("mx")),
                                "non_null": row.get("n"),
                                "last_365d": (recent or {}).get("count")}
        print(f"    {name:<22} min={d(row.get('mn'))} max={d(row.get('mx'))} "
              f"non_null={row.get('n')} last365={(recent or {}).get('count')}", flush=True)

    # Vocabularies
    entry["vocab"] = {}
    for vf in vocab_fields:
        if vf not in fields:
            continue
        res = q(qurl, {"where": "1=1", "groupByFieldsForStatistics": vf,
                       "outStatistics": json.dumps([{"statisticType": "count",
                                                     "onStatisticField": vf,
                                                     "outStatisticFieldName": "n"}]),
                       "orderByFields": "n DESC", "f": "json"})
        vals = [(f["attributes"].get(vf), f["attributes"].get("n"))
                for f in (res or {}).get("features", [])]
        entry["vocab"][vf] = [{"value": v, "count": c} for v, c in vals]
        print(f"\n    --- {vf} ({len(vals)}) ---", flush=True)
        for v, c in vals[:30]:
            print(f"        {c:>6}  {v!r}", flush=True)

    # How populated are the fields we actually want?
    entry["fill_rate"] = {}
    total = entry.get("count") or 0
    for sf in show_fields:
        if sf not in fields:
            continue
        w = (f"{sf} IS NOT NULL" if fields[sf] != "esriFieldTypeString"
             else f"{sf} IS NOT NULL AND {sf} <> ''")
        c = q(qurl, {"where": w, "returnCountOnly": "true", "f": "json"})
        got = (c or {}).get("count")
        entry["fill_rate"][sf] = got
        pct = f"{100 * got / total:.0f}%" if (total and got is not None) else "?"
        print(f"    fill {sf:<24} {got}/{total}  {pct}", flush=True)

    # Most recent rows, whole record
    best = max(entry["dates"].items(),
               key=lambda kv: (kv[1].get("last_365d") or 0), default=(None, {}))[0]
    entry["best_date_field"] = best
    print(f"\n    best_date_field={best}", flush=True)
    samp = q(qurl, {"where": "1=1", "outFields": "*", "returnGeometry": "true",
                    "outSR": 4326,
                    "orderByFields": f"{best} DESC" if best else "",
                    "resultRecordCount": 4, "f": "json"})
    entry["samples"] = (samp or {}).get("features", [])
    for feat in entry["samples"]:
        print("\n    " + "-" * 56, flush=True)
        for k, v in feat.get("attributes", {}).items():
            if v not in (None, "", 0):
                shown = d(v) if fields.get(k) == "esriFieldTypeDate" else v
                print(f"      {k:<24} {str(shown)[:100]}", flush=True)
        print(f"      GEOMETRY                 {feat.get('geometry')}", flush=True)

    OUT[key] = entry

p = os.path.join(os.path.dirname(__file__), "data", "vocab_leading.json")
os.makedirs(os.path.dirname(p), exist_ok=True)
with open(p, "w") as fh:
    json.dump(OUT, fh, indent=2, default=str)
hr(f"WROTE {p}")
