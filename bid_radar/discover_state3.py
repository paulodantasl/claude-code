"""
DISCOVER round 3 — the geocoder, and AHCA's real search endpoint.

Two questions left after round 2:

1. A GEOCODER IS NOW ACTUALLY NEEDED. PLAN.md §2 step 5 said it was not, and
   that was right while every source was a Tampa ArcGIS layer serving point
   geometry. The state files are not: DBPR and Sunbiz carry a street address
   and no coordinates, so without a geocoder their rows cannot be placed in a
   submarket and the scorer drops them on `outside_submarkets`. The US Census
   geocoder is free and needs no key — the only question is whether it answers
   a cloud runner.

2. AHCA. Round 2 found the per-county file exists only for Miami-Dade
   (Hillsborough 404s) and that a naive POST to FacilityLocateSearch returns
   400. That is the signature of an ASP.NET form wanting its antiforgery
   token, so this fetches the page, harvests the hidden fields, and posts them
   back properly.
"""
from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone

import requests

TIMEOUT = 60
UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"}
OUT: dict = {"retrieved_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}

#: Real Tampa addresses from signals already in the system, with the submarket
#: the ArcGIS geometry put them in. If the geocoder answers, its coordinates
#: must land in the same polygon — that is the test, not merely a 200.
KNOWN = [
    ("1050 Water St", "Tampa", "FL", "33602", "waterst"),
    ("1616 E 7th Ave", "Tampa", "FL", "33605", "ybor"),
    ("253 N West Shore Blvd", "Tampa", "FL", "33609", "airport"),
    ("12908 N Dale Mabry Hwy", "Tampa", "FL", "33618", None),
]


def hr(t: str) -> None:
    print("\n" + "=" * 72 + f"\n{t}\n" + "=" * 72, flush=True)


def census() -> None:
    hr("1. US Census geocoder — free, no key. Does it answer a runner?")
    OUT["census"] = {"one_line": [], "benchmark": None}
    url = "https://geocoding.geo.census.gov/geocoder/locations/onelineaddress"
    import sys
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    try:
        import geo
    except Exception:  # noqa: BLE001
        geo = None

    for street, city, state, zipc, expect in KNOWN:
        params = {"address": f"{street}, {city}, {state} {zipc}",
                  "benchmark": "Public_AR_Current", "format": "json"}
        rec = {"address": params["address"], "expected_hood": expect}
        try:
            r = requests.get(url, params=params, headers=UA, timeout=TIMEOUT)
            rec["status"] = r.status_code
            rec["content_type"] = r.headers.get("Content-Type", "")
            if r.status_code == 200 and "json" in rec["content_type"]:
                body = r.json()
                matches = (body.get("result") or {}).get("addressMatches") or []
                rec["n_matches"] = len(matches)
                if matches:
                    c = matches[0].get("coordinates") or {}
                    lon, lat = c.get("x"), c.get("y")
                    rec["lon"], rec["lat"] = lon, lat
                    rec["matched"] = matches[0].get("matchedAddress")
                    if geo and lon and lat:
                        rec["hood"] = geo.hood_of(lon, lat)
                        rec["agrees"] = (rec["hood"] == expect) if expect else None
            print(f"  {params['address'][:46]:<46} {rec.get('status')} "
                  f"-> {rec.get('hood')} (expected {expect}) "
                  f"{'OK' if rec.get('agrees') else ''}", flush=True)
        except Exception as exc:  # noqa: BLE001
            rec["error"] = f"{type(exc).__name__}: {exc}"
            print(f"  {params['address'][:46]:<46} !! {rec['error'][:60]}", flush=True)
        OUT["census"]["one_line"].append(rec)

    # The batch endpoint takes a CSV upload and is what a real run should use.
    hr("1b. Census BATCH endpoint — the one a real collector would use")
    batch_url = "https://geocoding.geo.census.gov/geocoder/locations/addressbatch"
    csv_body = "\n".join(
        f"{i},{s},{c},{st},{z}" for i, (s, c, st, z, _) in enumerate(KNOWN, 1))
    try:
        r = requests.post(batch_url,
                          data={"benchmark": "Public_AR_Current"},
                          files={"addressFile": ("a.csv", csv_body, "text/csv")},
                          headers=UA, timeout=TIMEOUT)
        OUT["census"]["batch"] = {"status": r.status_code,
                                  "bytes": len(r.content),
                                  "head": r.text[:400]}
        print(f"  batch: HTTP {r.status_code}  {len(r.content):,} bytes", flush=True)
        for line in r.text.splitlines()[:5]:
            print(f"    {line[:170]}", flush=True)
    except Exception as exc:  # noqa: BLE001
        OUT["census"]["batch"] = {"error": f"{type(exc).__name__}: {exc}"}
        print(f"  batch !! {type(exc).__name__}: {exc}", flush=True)


def ahca_form() -> None:
    hr("2. AHCA — post the search form with its antiforgery token")
    OUT["ahca"] = {}
    base = "https://quality.healthfinder.fl.gov"
    page = f"{base}/Facility-Search/FacilityLocateSearch"
    s = requests.Session()
    s.headers.update(UA)
    try:
        r = s.get(page, timeout=TIMEOUT)
    except Exception as exc:  # noqa: BLE001
        OUT["ahca"]["error"] = f"{type(exc).__name__}: {exc}"
        print(f"  !! {exc}", flush=True)
        return

    hidden = dict(re.findall(
        r'<input[^>]+type=["\']hidden["\'][^>]*name=["\']([^"\']+)["\'][^>]*'
        r'value=["\']([^"\']*)["\']', r.text, re.I))
    # name and value can appear in the other order
    hidden.update({n: v for v, n in re.findall(
        r'<input[^>]+type=["\']hidden["\'][^>]*value=["\']([^"\']*)["\'][^>]*'
        r'name=["\']([^"\']+)["\']', r.text, re.I)})
    OUT["ahca"]["hidden_fields"] = sorted(hidden)
    print(f"  hidden fields: {sorted(hidden)}", flush=True)

    selects = re.findall(r'<select[^>]+(?:name|id)=["\']([^"\']+)["\']', r.text, re.I)
    inputs = re.findall(
        r'<input[^>]+(?:name|id)=["\']([^"\']+)["\'][^>]*type=["\'](?:text|search)["\']',
        r.text, re.I)
    OUT["ahca"]["selects"] = sorted(set(selects))[:30]
    OUT["ahca"]["text_inputs"] = sorted(set(inputs))[:30]
    print(f"  selects: {sorted(set(selects))[:14]}", flush=True)
    print(f"  text inputs: {sorted(set(inputs))[:14]}", flush=True)

    # Any XHR endpoint named in the page's own script?
    urls = re.findall(r'url\s*:\s*["\']([^"\']+)["\']', r.text)
    urls += re.findall(r'["\'](/[A-Za-z0-9_\-]+/[A-Za-z0-9_\-/]*(?:Search|List|Data|Get)[A-Za-z0-9_\-/]*)["\']', r.text)
    OUT["ahca"]["script_urls"] = sorted(set(urls))[:30]
    print(f"  urls named in scripts: {sorted(set(urls))[:12]}", flush=True)

    for label, payload in (
        ("county only", {"County": "Hillsborough"}),
        ("county + type", {"County": "Hillsborough", "FacilityType": "0",
                           "ProviderType": "0"}),
    ):
        body = dict(hidden)
        body.update(payload)
        try:
            pr = s.post(page, data=body, timeout=TIMEOUT,
                        headers={"X-Requested-With": "XMLHttpRequest"})
            rec = {"status": pr.status_code, "bytes": len(pr.content),
                   "content_type": pr.headers.get("Content-Type", ""),
                   "hillsborough_mentions": pr.text.lower().count("hillsborough")}
            print(f"  POST {label:<14} {pr.status_code}  {rec['bytes']:>9,}  "
                  f"hillsborough x{rec['hillsborough_mentions']}", flush=True)
            OUT["ahca"][f"post_{label.replace(' ', '_')}"] = rec
        except Exception as exc:  # noqa: BLE001
            print(f"  POST {label} !! {type(exc).__name__}: {exc}", flush=True)


def main() -> int:
    for fn in (census, ahca_form):
        try:
            fn()
        except Exception as exc:  # noqa: BLE001
            print(f"!! {fn.__name__}: {type(exc).__name__}: {exc}", flush=True)
            OUT[fn.__name__] = {"error": f"{type(exc).__name__}: {exc}"}
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
    os.makedirs(out, exist_ok=True)
    with open(os.path.join(out, "vocab_state3.json"), "w") as fh:
        json.dump(OUT, fh, indent=2, default=str)
    hr("done — bid_radar/data/vocab_state3.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
