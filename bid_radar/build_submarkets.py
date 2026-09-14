"""
Builds bid_radar/submarkets.geojson from the core rings below.

Core rings are drawn from street and water boundaries (PLAN.md §2.1). Each is
then grown by a trade-area buffer:

  * 0.50 mi for the ISOLATED districts (wsmarina, dalemabry, airport) — a
    tenant two blocks outside Westshore Marina is still a Westshore Marina
    lead.
  * 0.10 mi for davis. Davis Islands is isolated, but it is an ISLAND: any
    meaningful buffer crosses open water. 0.50 mi reached Water Street and
    took Amalie Arena; 0.25 mi still crossed the Hillsborough channel and
    claimed 201 W Platt St, which is five blocks up the mainland in Hyde Park.
    The trade area stops at the shoreline.
  * 0.10 mi for the four CONTIGUOUS CBD districts (riverwalk, downtown,
    waterst, ybor) — these already share boundaries, so a half-mile buffer
    would make each swallow its neighbours. 0.10 mi is a half-block tolerance
    for addresses geocoded to a street centreline.

Where polygons still overlap (riverwalk and downtown share the Ashley Dr
frontage — the tracker itself files The Pendry under "Downtown Riverwalk" and
601 N Ashley under "Downtown Tampa", two labels for one place), PRECEDENCE in
geo.py decides, most specific first.

Run: python bid_radar/build_submarkets.py   (needs shapely; build-time only —
the runtime in geo.py has no dependencies).
"""
from __future__ import annotations

import json
import math
import os

from shapely.geometry import Polygon, mapping
from shapely.ops import transform

MI_PER_DEG_LAT = 69.0546
LAT0 = 27.95  # Tampa; used to scale longitude into a local equal-distance plane

# id -> (label, anchor, buffer_mi, [(lon, lat), ...])
CORES: dict[str, tuple[str, str, float, list[tuple[float, float]]]] = {
    # Ybor City historic district + the Gasworx corridor + Ybor Harbor.
    # Not a rectangle: the historic district stops at Adamo Dr, Gasworx runs
    # south from there to Channelside Dr between 14th St and the Ybor Channel,
    # and Ybor Harbor is the waterfront east of that. A rectangle here reaches
    # across Adamo into the Channel District and steals Water Street's permits
    # (verified: 1050 Water St and 1209 E Cumberland Ave both landed in it).
    # N Columbus Dr · W Nuccio Pkwy · E 26th St · S per the step below
    "ybor": ("Ybor City", "Gasworx, Live Nation, Ybor Harbor", 0.10, [
        (-82.4545, 27.9540), (-82.4510, 27.9540),   # Nuccio Pkwy at Adamo Dr
        (-82.4510, 27.9460), (-82.4380, 27.9460),   # Gasworx, down to Channelside Dr
        (-82.4380, 27.9425), (-82.4245, 27.9425),   # Ybor Harbor waterfront
        (-82.4245, 27.9668), (-82.4545, 27.9668)]), # Columbus Dr

    # East bank of the Hillsborough River: the Riverwalk frontage.
    # W river centreline · E one block east of Ashley Dr · N Cass/Waterworks · S Garrison Channel
    "riverwalk": ("Downtown Riverwalk", "The Pendry", 0.10, [
        (-82.4680, 27.9395), (-82.4585, 27.9395),
        (-82.4585, 27.9585), (-82.4680, 27.9585)]),

    # Downtown core. W Ashley Dr · E Nuccio Pkwy · N I-275 · S Selmon Expwy
    "downtown": ("Downtown Tampa", "Manor, ONE Tampa, Ora, 601 N Ashley", 0.10, [
        (-82.4650, 27.9400), (-82.4480, 27.9400),
        (-82.4480, 27.9570), (-82.4650, 27.9570)]),

    # Davis Islands, including the TGH campus at the north end.
    "davis": ("Davis Islands", "TGH Taneja Tower", 0.10, [
        (-82.4665, 27.9105), (-82.4405, 27.9105),
        (-82.4405, 27.9400), (-82.4665, 27.9400)]),

    # Water Street + Channel District.
    # W Florida Ave/Channelside · E 13th St · N Kennedy/Selmon · S Garrison Channel
    "waterst": ("Water Street", "Phase Two, Entertainment District", 0.10, [
        (-82.4535, 27.9365), (-82.4400, 27.9365),
        (-82.4400, 27.9470), (-82.4535, 27.9470)]),

    # Westshore Marina District. N Gandy Blvd · E Westshore Blvd · S/W Old Tampa Bay
    "wsmarina": ("Westshore Marina", "AQUA, Marina Pointe", 0.50, [
        (-82.5365, 27.8615), (-82.5175, 27.8615),
        (-82.5175, 27.8800), (-82.5365, 27.8800)]),

    # Rays stadium district: the HCC Dale Mabry campus site plus Raymond James.
    # W N Dale Mabry Hwy · E Himes Ave · S MLK Blvd · N past Tampa Bay Blvd
    "dalemabry": ("Dale Mabry", "Rays stadium district (Hillsborough College site)", 0.50, [
        (-82.5110, 27.9640), (-82.4960, 27.9640),
        (-82.4960, 27.9790), (-82.5110, 27.9790)]),

    # Tampa International + the Westshore business district.
    # W Memorial Hwy · E Lois Ave · S Kennedy Blvd · N past the terminal
    "airport": ("Airport / Westshore", "TPA expansion, Westshore business district", 0.50, [
        (-82.5600, 27.9420), (-82.5140, 27.9420),
        (-82.5140, 27.9880), (-82.5600, 27.9880)]),
}

# Most specific first: the first polygon that contains a point wins.
# Verified against real permit points from the live feed: 1050 Water St
# (Wagamama) and 1209 E Cumberland Ave -> waterst; 1 Tampa General Cir and
# 275 Bayshore Blvd -> davis; Amalie Arena -> waterst, not davis (Davis
# Islands' trade area crosses Garrison Channel, so waterst is tested first).
PRECEDENCE = ["waterst", "davis", "ybor", "riverwalk", "downtown",
              "wsmarina", "dalemabry", "airport"]


def _to_plane(lon: float, lat: float) -> tuple[float, float]:
    return lon * math.cos(math.radians(LAT0)), lat


def _from_plane(x: float, y: float) -> tuple[float, float]:
    return x / math.cos(math.radians(LAT0)), y


def buffer_miles(ring: list[tuple[float, float]], miles: float) -> list[list[float]]:
    poly = transform(lambda xs, ys: _to_plane(xs, ys), Polygon(ring))
    grown = poly.buffer(miles / MI_PER_DEG_LAT, quad_segs=8, join_style="round")
    back = transform(lambda xs, ys: _from_plane(xs, ys), grown)
    return [[round(x, 6), round(y, 6)] for x, y in back.exterior.coords]


def build() -> dict:
    feats = []
    for hid in PRECEDENCE:
        label, anchor, buf, ring = CORES[hid]
        feats.append({
            "type": "Feature",
            "properties": {
                "id": hid, "hood": label, "anchor": anchor,
                "buffer_mi": buf, "precedence": PRECEDENCE.index(hid),
                "core_ring": [[round(x, 6), round(y, 6)] for x, y in ring],
            },
            "geometry": {"type": "Polygon", "coordinates": [buffer_miles(ring, buf)]},
        })
    return {
        "type": "FeatureCollection",
        "name": "Ideal Construction tracked Tampa submarkets",
        "note": ("Core rings drawn from street/water boundaries; grown by the "
                 "per-feature buffer_mi. Overlaps are resolved by the "
                 "precedence property, lowest first."),
        "features": feats,
    }


if __name__ == "__main__":
    out = os.path.join(os.path.dirname(__file__), "submarkets.geojson")
    with open(out, "w") as fh:
        json.dump(build(), fh, indent=1)
    print(f"wrote {out}")
    for f in build()["features"]:
        xs = [c[0] for c in f["geometry"]["coordinates"][0]]
        ys = [c[1] for c in f["geometry"]["coordinates"][0]]
        print(f"  {f['properties']['id']:<10} buf={f['properties']['buffer_mi']} "
              f"lon[{min(xs):.4f},{max(xs):.4f}] lat[{min(ys):.4f},{max(ys):.4f}]")
