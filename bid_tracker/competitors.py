"""Competitor profiles from every tab in the DB.

    win_rate        = awards / bids
    pct_above_low   = median of (bid - low) / low across the bidder's tabs (0 = they were low)
    bid_ee          = median of bid / EE where the EE is a true engineer's estimate
    rank_pctile     = median of (price_rank - 1) / (N - 1); 0 = always low, 1 = always high
"""

from __future__ import annotations

import sqlite3
import statistics
from collections import defaultdict


def _median(values: list[float]) -> float | None:
    v = [x for x in values if x is not None]
    return statistics.median(v) if v else None


def profiles(conn: sqlite3.Connection, *, name: str | None = None, top: int = 20, since: str | None = None,
             include_ideal: bool = False) -> list[dict]:
    q = """SELECT c.*, s.agency_id FROM v_competitor_bids c
           JOIN solicitations s ON s.solicitation_id = c.solicitation_id
           WHERE s.award_basis IN ('low_bid', 'best_value')"""
    args: list = []
    if since:
        q += " AND c.bid_open_date >= ?"
        args.append(since)
    if name:
        q += " AND c.canonical_name LIKE ?"
        args.append(f"%{name}%")
    by: dict[int, list] = defaultdict(list)
    for r in conn.execute(q, args).fetchall():
        if r["is_ideal"] and not include_ideal:
            continue
        by[r["bidder_id"]].append(r)
    out = []
    for bidder_id, rs in by.items():
        wins = sum(1 for r in rs if r["is_awardee"])
        out.append({
            "bidder_id": bidder_id,
            "name": rs[0]["canonical_name"],
            "bids": len(rs),
            "wins": wins,
            "low_bids": sum(1 for r in rs if r["price_rank"] == 1),
            "win_rate": wins / len(rs),
            "pct_above_low": _median([r["pct_above_low"] for r in rs]),
            "bid_ee": _median([r["total_bid"] / r["engineers_estimate"] for r in rs
                               if r["ee_source"] == "ee" and r["engineers_estimate"]]),
            "rank_pctile": _median([(r["price_rank"] - 1) / (r["n_bidders"] - 1) for r in rs if r["n_bidders"] > 1]),
            "agencies": sorted({r["agency_id"] for r in rs}),
            "counties": sorted({r["county"] for r in rs if r["county"]}),
            "project_types": sorted({r["project_type"] for r in rs}),
            "last_bid": max(r["bid_open_date"] for r in rs),
        })
    out.sort(key=lambda p: (-p["bids"], -p["wins"], p["name"]))
    return out[:top] if top else out


def head_to_head(conn: sqlite3.Connection) -> list[dict]:
    """Competitors Ideal has met on the same tab: how often Ideal priced lower, and by how much."""
    rows = conn.execute(
        """SELECT o.solicitation_id, o.bidder_id, o.canonical_name, o.total_bid, o.is_ideal
           FROM v_bid_order o
           WHERE o.solicitation_id IN (SELECT solicitation_id FROM v_bid_order WHERE is_ideal = 1)"""
    ).fetchall()
    ideal_bid = {r["solicitation_id"]: r["total_bid"] for r in rows if r["is_ideal"]}
    by: dict[int, list] = defaultdict(list)
    for r in rows:
        if not r["is_ideal"]:
            by[r["bidder_id"]].append(r)
    out = []
    for _bid, rs in by.items():
        ratios = [ideal_bid[r["solicitation_id"]] / r["total_bid"] for r in rs]
        out.append({
            "name": rs[0]["canonical_name"],
            "shared_tabs": len(rs),
            "ideal_lower": sum(1 for x in ratios if x < 1),
            "ideal_over_them": statistics.median(ratios),
        })
    out.sort(key=lambda d: (-d["shared_tabs"], d["name"]))
    return out
