"""Disaster / term-contract rate cards: market bands per service and size bucket, and cliff checks.

Effective $/SF: unit 'sf' is already $/SF. A lump-sum bucket is converted at the bucket
midpoint ((min + max) / 2) and labelled derived. Open-ended lump buckets have no $/SF.

Cliff check (a scoring lesson from past term-contract bids): at each bucket boundary compare the next bucket's price at
its smallest size with this bucket's price at its largest size. A jump over CLIFF_RATIO for one
extra square foot reads as a broken price curve to evaluators.
"""

from __future__ import annotations

import sqlite3
from collections import defaultdict

from bid_tracker.stats import quartiles

CLIFF_RATIO = 1.25


def effective_psf(unit: str, price: float, size_min: float | None, size_max: float | None) -> tuple[float | None, bool]:
    unit = (unit or "").lower()
    if unit in ("sf", "sqft", "per sf", "$/sf"):
        return price, False
    if unit in ("lump", "ls", "lump sum") and size_max:
        mid = ((size_min or 0) + size_max) / 2
        return (price / mid, True) if mid else (None, True)
    return None, False


def price_at(unit: str, price: float, size: float) -> float | None:
    unit = (unit or "").lower()
    if unit in ("sf", "sqft", "per sf", "$/sf"):
        return price * size
    if unit in ("lump", "ls", "lump sum"):
        return price
    return None


def bucket_label(lo: float | None, hi: float | None) -> str:
    lo_s = f"{int(lo):,}" if lo is not None else "0"
    return f"{lo_s}-{int(hi):,} sf" if hi else f"{lo_s}+ sf"


def load_rates(conn: sqlite3.Connection, service: str | None = None, since: str | None = None) -> list[dict]:
    q = """SELECT r.*, s.sol_ref, s.bid_open_date, s.region, a.agency_type, b.canonical_name, b.is_ideal,
                  EXISTS(SELECT 1 FROM bids x WHERE x.solicitation_id = r.solicitation_id
                         AND x.bidder_id = r.bidder_id AND x.is_awardee = 1)
                  OR s.awardee_bidder_id = r.bidder_id AS is_awardee
           FROM rate_cards r
           JOIN solicitations s ON s.solicitation_id = r.solicitation_id
           JOIN agencies a ON a.agency_id = s.agency_id
           JOIN bidders b ON b.bidder_id = r.bidder_id WHERE 1=1"""
    args: list = []
    if service:
        q += " AND r.service = ?"
        args.append(service)
    if since:
        q += " AND s.bid_open_date >= ?"
        args.append(since)
    out = []
    for r in conn.execute(q, args).fetchall():
        d = dict(r)
        d["psf"], d["psf_derived"] = effective_psf(r["unit"], r["price"], r["size_min_sf"], r["size_max_sf"])
        d["bucket"] = bucket_label(r["size_min_sf"], r["size_max_sf"])
        out.append(d)
    return out


def percentile_rank(value: float, values: list[float]) -> float | None:
    if not values:
        return None
    return sum(1 for v in values if v <= value) / len(values)


def rate_bands(conn: sqlite3.Connection, service: str | None = None, since: str | None = None) -> list[dict]:
    rows = load_rates(conn, service, since)
    groups: dict[tuple, list[dict]] = defaultdict(list)
    for r in rows:
        if r["psf"] is not None:
            groups[(r["service"], r["size_min_sf"] or 0, r["bucket"])].append(r)
    out = []
    for (svc, _lo, bucket), rs in sorted(groups.items()):
        all_psf = [r["psf"] for r in rs if not r["is_ideal"]]
        ideal = [r["psf"] for r in rs if r["is_ideal"]]
        out.append({
            "service": svc, "bucket": bucket,
            "all_bidders": quartiles(all_psf),
            "awardees": quartiles([r["psf"] for r in rs if r["is_awardee"] and not r["is_ideal"]]),
            "derived": any(r["psf_derived"] for r in rs),
            "contracts": len({r["sol_ref"] for r in rs}),
            "ideal_psf": ideal[-1] if ideal else None,
            "ideal_percentile": percentile_rank(ideal[-1], all_psf) if ideal else None,
        })
    return out


def cliffs(conn: sqlite3.Connection, sol_ref: str | None = None, ratio: float = CLIFF_RATIO) -> list[dict]:
    rows = load_rates(conn)
    if sol_ref:
        rows = [r for r in rows if r["sol_ref"] == sol_ref]
    by: dict[tuple, list[dict]] = defaultdict(list)
    for r in rows:
        if r["size_min_sf"] is not None:
            by[(r["sol_ref"], r["canonical_name"], r["service"], r["service_desc"])].append(r)
    found = []
    for (ref, name, svc, _desc), rs in by.items():
        rs.sort(key=lambda r: r["size_min_sf"])
        for a, b in zip(rs, rs[1:]):
            # Only adjacent buckets (next one starts within a square foot of this one's top).
            if not a["size_max_sf"] or b["size_min_sf"] - a["size_max_sf"] > 1:
                continue
            pa = price_at(a["unit"], a["price"], a["size_max_sf"])
            pb = price_at(b["unit"], b["price"], b["size_min_sf"])
            if not pa or not pb:
                continue
            jump = pb / pa
            if jump > ratio or jump < 1 / ratio:
                found.append({
                    "sol_ref": ref, "bidder": name, "service": svc,
                    "from_bucket": a["bucket"], "to_bucket": b["bucket"],
                    "price_at_top": pa, "price_at_next": pb, "jump": jump,
                })
    return found
