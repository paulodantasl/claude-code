"""
Address -> coordinates, so the state files can reach a submarket.

PLAN.md §2 step 5 said a geocoder was not needed, and while every source was a
Tampa ArcGIS layer that was right — those serve point geometry. The state files
do not: DBPR and Sunbiz carry a street address and nothing else, so without
this their rows can never be placed and the scorer drops every one of them on
`outside_submarkets`.

The US Census geocoder is free, needs no key, and answered a GitHub runner on
2026-09-14. It was not trusted on a 200 alone — it was checked against four
Tampa addresses whose submarket the ArcGIS geometry already knew:

    1616 E 7th Ave          -> ybor      (agreed)
    253 N West Shore Blvd   -> airport   (agreed)
    12908 N Dale Mabry Hwy  -> outside   (agreed)
    1050 Water St           -> "Tie"     (no coordinates returned)

That last one is the honest limit of this source and the reason nothing here
guesses. Water Street is new construction and the TIGER road file has not
caught up, so the Census returns an ambiguous "Tie" rather than a point. A row
that cannot be resolved keeps `hood: None` and `needs_geocode: True`; it is
never placed by ZIP, because 33602 alone spans Downtown, the Riverwalk, Water
Street and the Channel District.

Results are cached on the data branch, so an address is paid for once.
"""
from __future__ import annotations

import csv
import io
import json
import os
import re
from datetime import datetime, timezone

import requests

BATCH_URL = "https://geocoding.geo.census.gov/geocoder/locations/addressbatch"
BENCHMARK = "Public_AR_Current"
CACHE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                          "data", "geocode_cache.json")
BATCH_SIZE = int(os.environ.get("GEOCODE_BATCH", "500"))
MAX_BATCHES = int(os.environ.get("GEOCODE_MAX_BATCHES", "8"))
TIMEOUT = 120

#: A miss is cached too, so a bad address is not re-sent every run. It is
#: stored as this rather than as null so a miss is distinguishable from an
#: address that has simply never been tried.
MISS = "miss"

_WS = re.compile(r"\s+")


def key(street: str, city: str, state: str, zipc: str) -> str:
    parts = [_WS.sub(" ", (p or "").strip().upper())
             for p in (street, city, state, zipc)]
    return "|".join(parts)


def load_cache() -> dict:
    try:
        with open(CACHE_PATH) as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return {}


def save_cache(cache: dict) -> None:
    os.makedirs(os.path.dirname(CACHE_PATH), exist_ok=True)
    hits = sum(1 for k, v in cache.items()
               if not k.startswith("_") and v != MISS)
    cache["_meta"] = {
        "updated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "addresses": len([k for k in cache if not k.startswith("_")]),
        "resolved": hits,
        "source": "US Census geocoder, benchmark " + BENCHMARK,
    }
    with open(CACHE_PATH, "w") as fh:
        json.dump(cache, fh, separators=(",", ":"), sort_keys=True)


def _post_batch(rows: list[tuple[str, str, str, str, str]]) -> dict[str, tuple[float, float]]:
    """rows: (id, street, city, state, zip). Returns {id: (lon, lat)}."""
    buf = io.StringIO()
    w = csv.writer(buf)
    for r in rows:
        w.writerow(r)
    try:
        resp = requests.post(
            BATCH_URL,
            data={"benchmark": BENCHMARK},
            files={"addressFile": ("addresses.csv", buf.getvalue(), "text/csv")},
            timeout=TIMEOUT)
    except Exception as exc:  # noqa: BLE001
        print(f"    geocode batch failed: {type(exc).__name__}: {exc}", flush=True)
        return {}
    if resp.status_code != 200:
        print(f"    geocode batch HTTP {resp.status_code}", flush=True)
        return {}

    out: dict[str, tuple[float, float]] = {}
    for row in csv.reader(io.StringIO(resp.text)):
        # id, input, status, [match type, matched address, "lon,lat", tiger id, side]
        if len(row) < 6 or row[2] != "Match":
            continue          # "Tie" and "No_Match" resolve to nothing, by design
        try:
            lon, lat = (float(v) for v in row[5].split(","))
        except (ValueError, IndexError):
            continue
        out[row[0]] = (lon, lat)
    return out


def resolve(addresses: list[tuple[str, str, str, str]], *,
            use_cache: bool = True) -> dict[str, tuple[float, float] | None]:
    """Batch-resolve. Returns {key: (lon, lat) | None} for every address given."""
    cache = load_cache() if use_cache else {}
    wanted = {key(*a): a for a in addresses if a and a[0]}
    todo = [(k, a) for k, a in wanted.items() if k not in cache]

    if todo:
        print(f"    geocoding {len(todo)} new addresses "
              f"({len(wanted) - len(todo)} cached)", flush=True)
    for i in range(0, min(len(todo), BATCH_SIZE * MAX_BATCHES), BATCH_SIZE):
        chunk = todo[i:i + BATCH_SIZE]
        rows = [(str(n), a[0], a[1], a[2], a[3]) for n, (_, a) in enumerate(chunk)]
        got = _post_batch(rows)
        for n, (k, _) in enumerate(chunk):
            hit = got.get(str(n))
            cache[k] = list(hit) if hit else MISS
        print(f"      batch {i // BATCH_SIZE + 1}: {len(got)}/{len(chunk)} resolved",
              flush=True)
        if use_cache:
            save_cache(cache)

    out: dict[str, tuple[float, float] | None] = {}
    for k in wanted:
        v = cache.get(k)
        out[k] = tuple(v) if isinstance(v, list) and len(v) == 2 else None
    return out


def resolve_signals(signals: list[dict]) -> dict:
    """Fill `lat`/`lon`/`hood` on every signal that asked for it, in place."""
    import geo

    todo = [s for s in signals
            if s.get("needs_geocode") and s.get("address")]
    stats = {"wanted": len(todo), "resolved": 0, "placed": 0}
    if not todo:
        return stats

    addresses = []
    for s in todo:
        street = (s.get("address") or "").split(",")[0].strip()
        city = ((s.get("address") or "").split(",")[1].strip()
                if "," in (s.get("address") or "") else "Tampa")
        addresses.append((street, city, "FL", s.get("zip") or ""))

    found = resolve(addresses)
    for s, a in zip(todo, addresses):
        hit = found.get(key(*a))
        if not hit:
            continue
        lon, lat = hit
        s["lon"], s["lat"] = lon, lat
        s["needs_geocode"] = False
        s["geocoded_by"] = "census"
        stats["resolved"] += 1
        hood = geo.hood_of(lon, lat)
        if hood:
            s["hood"] = hood
            stats["placed"] += 1
    print(f"    geocoded {stats['resolved']}/{stats['wanted']}; "
          f"{stats['placed']} landed in a tracked submarket", flush=True)
    return stats
