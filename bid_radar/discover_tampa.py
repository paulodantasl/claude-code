"""
DISCOVER step for PLAN.md §3 source #1 — City of Tampa permits ArcGIS FeatureServer.

Runs only in GitHub Actions (the Claude sandbox blocks arcgis.tampagov.net).
Establishes, from the service itself rather than from guesses:

  * which services/layers exist under the Planning folder
  * the layer's geometry type and spatial reference
  * every field (name, type, alias)
  * which date field is populated, and its min/max
  * distinct values + counts for every low-cardinality string field
  * three full sample features from the last 90 days

Everything is printed to stdout (read via mcp__github__get_job_logs) and
written to bid_radar/data/vocab_tampa.json.
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timedelta, timezone

import requests

SERVICE = os.environ.get(
    "TAMPA_SERVICE",
    "https://arcgis.tampagov.net/arcgis/rest/services/Planning/PermitsAll/FeatureServer",
)
LAYER = int(os.environ.get("TAMPA_LAYER", "0"))
DAYS_BACK = int(os.environ.get("DAYS_BACK", "90"))
TIMEOUT = 60

OUT = {"service": SERVICE, "layer": LAYER, "retrieved_at": datetime.now(timezone.utc).isoformat()}


def hr(title: str) -> None:
    print("\n" + "=" * 70, flush=True)
    print(title, flush=True)
    print("=" * 70, flush=True)


def get(url: str, params: dict | None = None) -> dict:
    r = requests.get(url, params=params or {}, timeout=TIMEOUT)
    r.raise_for_status()
    body = r.json()
    if isinstance(body, dict) and "error" in body:
        raise RuntimeError(f"ArcGIS error for {r.url}: {body['error']}")
    return body


def try_get(url: str, params: dict | None = None):
    try:
        return get(url, params)
    except Exception as exc:  # noqa: BLE001 - discovery must never abort
        print(f"  !! {type(exc).__name__}: {exc}", flush=True)
        return None


# --------------------------------------------------------------------------
hr("1. Planning folder — what services exist")
folder = try_get("https://arcgis.tampagov.net/arcgis/rest/services/Planning", {"f": "json"})
if folder:
    names = [s.get("name") for s in folder.get("services", [])]
    OUT["planning_services"] = names
    for n in names:
        print(f"  {n}", flush=True)

hr("2. Service root")
root = try_get(SERVICE, {"f": "json"})
if root:
    OUT["service_layers"] = [
        {"id": lyr.get("id"), "name": lyr.get("name"), "geometryType": lyr.get("geometryType")}
        for lyr in root.get("layers", [])
    ]
    print(f"  currentVersion={root.get('currentVersion')}  "
          f"maxRecordCount={root.get('maxRecordCount')}", flush=True)
    for lyr in OUT["service_layers"]:
        print(f"  layer {lyr['id']}: {lyr['name']} ({lyr['geometryType']})", flush=True)

hr(f"3. Layer {LAYER} metadata")
meta = try_get(f"{SERVICE}/{LAYER}", {"f": "json"})
if not meta:
    print("FATAL: layer metadata unreachable", flush=True)
    sys.exit(1)

fields = meta.get("fields", [])
OUT["layer_name"] = meta.get("name")
OUT["geometryType"] = meta.get("geometryType")
OUT["spatialReference"] = meta.get("extent", {}).get("spatialReference")
OUT["maxRecordCount"] = meta.get("maxRecordCount")
OUT["supportsPagination"] = meta.get("advancedQueryCapabilities", {}).get("supportsPagination")
OUT["fields"] = [
    {"name": f["name"], "type": f["type"], "alias": f.get("alias"), "length": f.get("length")}
    for f in fields
]
print(f"  name={OUT['layer_name']}", flush=True)
print(f"  geometryType={OUT['geometryType']}  sr={OUT['spatialReference']}", flush=True)
print(f"  maxRecordCount={OUT['maxRecordCount']}  pagination={OUT['supportsPagination']}", flush=True)
print(f"  {len(fields)} fields:", flush=True)
for f in OUT["fields"]:
    print(f"    {f['name']:<32} {f['type'].replace('esriFieldType',''):<12} "
          f"len={f['length']}  alias={f['alias']}", flush=True)

date_fields = [f["name"] for f in OUT["fields"] if f["type"] == "esriFieldTypeDate"]
str_fields = [f for f in OUT["fields"] if f["type"] == "esriFieldTypeString"]
num_fields = [f["name"] for f in OUT["fields"]
              if f["type"] in ("esriFieldTypeDouble", "esriFieldTypeInteger",
                               "esriFieldTypeSingle", "esriFieldTypeSmallInteger")]
OUT["date_fields"] = date_fields
OUT["numeric_fields"] = num_fields

QUERY = f"{SERVICE}/{LAYER}/query"

hr("4. Total record count")
cnt = try_get(QUERY, {"where": "1=1", "returnCountOnly": "true", "f": "json"})
if cnt:
    OUT["total_count"] = cnt.get("count")
    print(f"  total features: {cnt.get('count')}", flush=True)

hr("5. Date fields — populated range and 90-day volume")
since = datetime.now(timezone.utc) - timedelta(days=DAYS_BACK)
since_sql = since.strftime("%Y-%m-%d")
OUT["date_field_stats"] = {}
for df in date_fields:
    stats = try_get(QUERY, {
        "where": "1=1",
        "outStatistics": json.dumps([
            {"statisticType": "min", "onStatisticField": df, "outStatisticFieldName": "mn"},
            {"statisticType": "max", "onStatisticField": df, "outStatisticFieldName": "mx"},
            {"statisticType": "count", "onStatisticField": df, "outStatisticFieldName": "n"},
        ]),
        "f": "json",
    })
    row = (stats or {}).get("features", [{}])[0].get("attributes", {})

    def ms(v):
        try:
            return datetime.fromtimestamp(v / 1000, timezone.utc).strftime("%Y-%m-%d")
        except Exception:  # noqa: BLE001
            return None

    recent = try_get(QUERY, {
        "where": f"{df} >= DATE '{since_sql}'",
        "returnCountOnly": "true", "f": "json",
    })
    entry = {
        "min": ms(row.get("mn")), "max": ms(row.get("mx")),
        "non_null": row.get("n"),
        f"last_{DAYS_BACK}d": (recent or {}).get("count"),
    }
    OUT["date_field_stats"][df] = entry
    print(f"  {df:<28} min={entry['min']} max={entry['max']} "
          f"non_null={entry['non_null']} last{DAYS_BACK}d={entry[f'last_{DAYS_BACK}d']}", flush=True)

hr("6. String-field vocabularies (distinct values + counts, whole layer)")
OUT["vocab"] = {}
for f in str_fields:
    name = f["name"]
    if (f.get("length") or 0) > 120:          # free-text: descriptions, not vocabulary
        print(f"  {name}: skipped (length={f.get('length')}, free text)", flush=True)
        continue
    res = try_get(QUERY, {
        "where": "1=1",
        "groupByFieldsForStatistics": name,
        "outStatistics": json.dumps([
            {"statisticType": "count", "onStatisticField": name, "outStatisticFieldName": "n"}
        ]),
        "orderByFields": "n DESC",
        "resultRecordCount": 300,
        "f": "json",
    })
    if not res:
        continue
    vals = [(feat["attributes"].get(name), feat["attributes"].get("n"))
            for feat in res.get("features", [])]
    OUT["vocab"][name] = [{"value": v, "count": n} for v, n in vals]
    print(f"\n  --- {name} ({len(vals)} distinct) ---", flush=True)
    for v, n in vals[:80]:
        print(f"      {n:>8}  {v}", flush=True)
    if len(vals) > 80:
        print(f"      ... {len(vals) - 80} more (full list in vocab_tampa.json)", flush=True)

hr(f"7. Three sample features from the last {DAYS_BACK} days (outSR=4326)")
best_date = None
for df in date_fields:
    s = OUT["date_field_stats"].get(df, {})
    if s.get(f"last_{DAYS_BACK}d"):
        best_date = df
        break
OUT["best_date_field"] = best_date
print(f"  best_date_field = {best_date}", flush=True)

sample = try_get(QUERY, {
    "where": f"{best_date} >= DATE '{since_sql}'" if best_date else "1=1",
    "outFields": "*",
    "returnGeometry": "true",
    "outSR": 4326,
    "orderByFields": f"{best_date} DESC" if best_date else "",
    "resultRecordCount": 3,
    "f": "json",
})
if sample:
    OUT["sample_features"] = sample.get("features", [])
    OUT["sample_spatialReference"] = sample.get("spatialReference")
    print(f"  returned spatialReference={sample.get('spatialReference')}", flush=True)
    for feat in sample.get("features", []):
        print("\n  " + "-" * 60, flush=True)
        for k, v in feat.get("attributes", {}).items():
            if v not in (None, ""):
                print(f"    {k:<32} {str(v)[:120]}", flush=True)
        print(f"    GEOMETRY                         {feat.get('geometry')}", flush=True)

os.makedirs(os.path.join(os.path.dirname(__file__), "data"), exist_ok=True)
path = os.path.join(os.path.dirname(__file__), "data", "vocab_tampa.json")
with open(path, "w") as fh:
    json.dump(OUT, fh, indent=2, default=str)
hr(f"WROTE {path}")
