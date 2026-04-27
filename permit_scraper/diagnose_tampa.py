"""Diagnose Tampa ArcGIS API — find correct fields and query syntax."""
import requests, json, warnings
warnings.filterwarnings("ignore")

BASE = "https://arcgis.tampagov.net/arcgis/rest/services/Planning/PermitsAll/FeatureServer"

print("=== 1. Service info ===")
r = requests.get(BASE, params={"f": "json"}, timeout=20)
print(f"Status: {r.status_code}")
if r.ok:
    d = r.json()
    layers = d.get("layers", [])
    print(f"Layers: {[(l['id'], l['name']) for l in layers]}")

print("\n=== 2. Layer 0 fields ===")
r = requests.get(f"{BASE}/0", params={"f": "json"}, timeout=20)
print(f"Status: {r.status_code}")
if r.ok:
    d = r.json()
    fields = d.get("fields", [])
    print(f"Fields ({len(fields)}):")
    for f in fields:
        print(f"  {f['name']} ({f['type']})")
    caps = d.get("capabilities", "")
    print(f"Capabilities: {caps}")
    adv = d.get("advancedQueryCapabilities", {})
    print(f"supportsOrderBy: {adv.get('supportsOrderBy')}")
    print(f"supportsPagination: {adv.get('supportsPagination')}")

print("\n=== 3. Simple query (no orderBy, no where) ===")
r = requests.get(f"{BASE}/0/query", params={
    "where": "1=1", "outFields": "OBJECTID", "resultRecordCount": 3, "f": "json"
}, timeout=20)
print(f"Status: {r.status_code}  body: {r.text[:300]}")

print("\n=== 4. Query without orderByFields ===")
r = requests.get(f"{BASE}/0/query", params={
    "where": "1=1", "outFields": "*", "resultRecordCount": 3, "f": "json"
}, timeout=20)
print(f"Status: {r.status_code}  body: {r.text[:500]}")
