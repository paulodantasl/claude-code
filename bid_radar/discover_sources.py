"""
DISCOVER round 2 (PLAN.md §3) — answers the questions round 1 raised:

  * PermitsAll carries only PROJECTSTATUS in {Issued, Revision} and has no
    valuation / applicant / contractor field. So: how much warning does
    CREATEDDATE give over LASTUPDATE, and do PROJECTNAME1/2 name the tenant?
  * The Planning folder advertises AlcoholBeverage, ActiveEntitlementLocations,
    CRACommercialInitiative and LiveLocalAct — none of which PLAN.md knew
    about. Are any of them an *earlier* signal than a permit?
  * Is URL a per-permit deep link or a constant?

Runs in GitHub Actions only. Writes bid_radar/data/vocab_sources.json.
"""
from __future__ import annotations

import json
import os
from collections import Counter
from datetime import datetime, timedelta, timezone

import requests

ROOT = "https://arcgis.tampagov.net/arcgis/rest/services"
PERMITS = f"{ROOT}/Planning/PermitsAll/FeatureServer/0/query"
TIMEOUT = 60
OUT: dict = {"retrieved_at": datetime.now(timezone.utc).isoformat()}


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


def ms(v):
    try:
        return datetime.fromtimestamp(v / 1000, timezone.utc).date().isoformat()
    except Exception:  # noqa: BLE001
        return None


# ---------------------------------------------------------------- 1
hr("1. Other Planning services — do any carry an EARLIER signal?")
OUT["services"] = {}
for svc in ["AlcoholBeverage", "ActiveEntitlementLocations", "CRACommercialInitiative",
            "LiveLocalAct", "PlanningViewer", "SingleFamilyPermits"]:
    for kind in ("FeatureServer", "MapServer"):
        root = q(f"{ROOT}/Planning/{svc}/{kind}", {"f": "json"})
        if not root:
            continue
        print(f"\n  --- Planning/{svc}/{kind} ---", flush=True)
        entry = {"layers": []}
        for lyr in root.get("layers", []) + root.get("tables", []):
            lid = lyr.get("id")
            meta = q(f"{ROOT}/Planning/{svc}/{kind}/{lid}", {"f": "json"})
            if not meta:
                continue
            cnt = q(f"{ROOT}/Planning/{svc}/{kind}/{lid}/query",
                    {"where": "1=1", "returnCountOnly": "true", "f": "json"})
            flds = [f"{f['name']}:{f['type'].replace('esriFieldType','')}"
                    for f in meta.get("fields", [])]
            print(f"    layer {lid}: {meta.get('name')}  n={(cnt or {}).get('count')}", flush=True)
            print(f"      fields: {', '.join(flds)}", flush=True)
            samp = q(f"{ROOT}/Planning/{svc}/{kind}/{lid}/query",
                     {"where": "1=1", "outFields": "*", "returnGeometry": "false",
                      "resultRecordCount": 2, "f": "json"})
            for feat in (samp or {}).get("features", [])[:2]:
                print(f"      sample: {json.dumps(feat.get('attributes'), default=str)[:900]}",
                      flush=True)
            entry["layers"].append(
                {"id": lid, "name": meta.get("name"), "count": (cnt or {}).get("count"),
                 "fields": flds,
                 "sample": [f.get("attributes") for f in (samp or {}).get("features", [])[:2]]}
            )
        OUT["services"][f"{svc}/{kind}"] = entry
        break

# ---------------------------------------------------------------- 2
hr("2. PermitsAll — RECORDTYPE x PROJECTSTATUS over the last 90d (CREATEDDATE)")
since = (datetime.now(timezone.utc) - timedelta(days=90)).strftime("%Y-%m-%d")
res = q(PERMITS, {
    "where": f"CREATEDDATE >= DATE '{since}'",
    "groupByFieldsForStatistics": "RECORDTYPE,PROJECTSTATUS",
    "outStatistics": json.dumps([{"statisticType": "count",
                                  "onStatisticField": "OBJECTID",
                                  "outStatisticFieldName": "n"}]),
    "f": "json",
})
OUT["recordtype_x_status_90d"] = [f["attributes"] for f in (res or {}).get("features", [])]
for a in OUT["recordtype_x_status_90d"]:
    print(f"  {a['n']:>5}  {a.get('PROJECTSTATUS'):<10} {a.get('RECORDTYPE')}", flush=True)

# ---------------------------------------------------------------- 3
hr("3. Commercial alterations — OCCUPANCYCATEGORY breakdown (all time)")
res = q(PERMITS, {
    "where": "RECORDTYPE LIKE 'Commercial%'",
    "groupByFieldsForStatistics": "RECORDTYPE,OCCUPANCYCATEGORY",
    "outStatistics": json.dumps([{"statisticType": "count",
                                  "onStatisticField": "OBJECTID",
                                  "outStatisticFieldName": "n"}]),
    "orderByFields": "n DESC", "f": "json",
})
OUT["commercial_occupancy"] = [f["attributes"] for f in (res or {}).get("features", [])]
for a in OUT["commercial_occupancy"]:
    print(f"  {a['n']:>5}  {a.get('OCCUPANCYCATEGORY')}   [{a.get('RECORDTYPE')}]", flush=True)

# ---------------------------------------------------------------- 4
hr("4. Commercial records — 25 most recent by CREATEDDATE, full attributes")
res = q(PERMITS, {
    "where": "RECORDTYPE LIKE 'Commercial%'",
    "outFields": "*", "returnGeometry": "true", "outSR": 4326,
    "orderByFields": "CREATEDDATE DESC", "resultRecordCount": 25, "f": "json",
})
feats = (res or {}).get("features", [])
OUT["commercial_recent"] = feats
urls, lags = set(), []
for f in feats:
    a = f["attributes"]
    cd, lu = a.get("CREATEDDATE"), a.get("LASTUPDATE")
    if cd and lu:
        lags.append(round((lu - cd) / 86400000))
    urls.add(a.get("URL"))
    print(f"\n  {a.get('RECORD_ID')}  created={ms(cd)} lastupdate={ms(lu)} "
          f"status={a.get('PROJECTSTATUS')}", flush=True)
    print(f"     type={a.get('RECORDTYPE')}", flush=True)
    print(f"     occ ={a.get('OCCUPANCYCATEGORY')} / {a.get('OCCUPANCYTYPE')}", flush=True)
    print(f"     nm1 ={a.get('PROJECTNAME1')!r}", flush=True)
    print(f"     nm2 ={a.get('PROJECTNAME2')!r}", flush=True)
    print(f"     desc={a.get('PROJECTDESCRIPTION')!r}", flush=True)
    print(f"     addr={a.get('ADDRESS')!r} unit={a.get('UNIT')!r} zip={a.get('ZIP')} "
          f"hood={a.get('NEIGHBORHOOD')!r} sf={a.get('NEWCONSTRUCTIONSF')}", flush=True)
    print(f"     url ={a.get('URL')}", flush=True)
    print(f"     geom={f.get('geometry')}", flush=True)

hr("5. Derived")
OUT["url_distinct_in_sample"] = len(urls)
OUT["created_to_lastupdate_lag_days"] = lags
print(f"  distinct URL values across {len(feats)} records: {len(urls)}", flush=True)
if lags:
    lags_s = sorted(lags)
    OUT["lag_median"] = lags_s[len(lags_s) // 2]
    print(f"  CREATEDDATE->LASTUPDATE lag days: min={lags_s[0]} "
          f"median={OUT['lag_median']} max={lags_s[-1]}", flush=True)
    print(f"  distribution: {dict(Counter(lags_s))}", flush=True)

os.makedirs(os.path.join(os.path.dirname(__file__), "data"), exist_ok=True)
p = os.path.join(os.path.dirname(__file__), "data", "vocab_sources.json")
with open(p, "w") as fh:
    json.dump(OUT, fh, indent=2, default=str)
hr(f"WROTE {p}")
