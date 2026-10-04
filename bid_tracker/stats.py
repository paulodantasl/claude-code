"""Per-tabulation statistics. With responsive totals sorted b1 <= b2 <= ... <= bN:

    gap        = (b2 - b1) / b1          money left on the table by the low bidder
    low_median = b1 / median(b)
    low_ee     = b1 / EE                 only when the EE is a true engineer's estimate
    cv         = stdev(b) / mean(b)      sample stdev; how tightly the field priced
    range_pct  = (bN - b1) / b1
    low_psf    = b1 / GSF
"""

from __future__ import annotations

import sqlite3
import statistics
from dataclasses import asdict, dataclass


@dataclass
class TabStats:
    n: int
    low: float | None = None
    second: float | None = None
    high: float | None = None
    median: float | None = None
    gap: float | None = None
    low_median: float | None = None
    low_ee: float | None = None
    cv: float | None = None
    range_pct: float | None = None
    low_psf: float | None = None

    def as_dict(self) -> dict:
        return asdict(self)


def tab_stats(totals: list[float], ee: float | None = None, gsf: float | None = None) -> TabStats:
    b = sorted(t for t in totals if t and t > 0)
    s = TabStats(n=len(b))
    if not b:
        return s
    s.low, s.high = b[0], b[-1]
    s.median = statistics.median(b)
    s.low_median = b[0] / s.median
    s.range_pct = (b[-1] - b[0]) / b[0]
    if len(b) >= 2:
        s.second = b[1]
        s.gap = (b[1] - b[0]) / b[0]
        s.cv = statistics.stdev(b) / statistics.fmean(b)
    if ee:
        s.low_ee = b[0] / ee
    if gsf:
        s.low_psf = b[0] / gsf
    return s


def quartiles(values: list[float]) -> dict:
    """p25/p50/p75 for n >= 3; raw sorted values below that (too few for percentiles)."""
    v = sorted(x for x in values if x is not None)
    out = {"n": len(v)}
    if len(v) >= 3:
        p25, p50, p75 = statistics.quantiles(v, n=4, method="inclusive")
        out.update(p25=p25, p50=p50, p75=p75)
    elif v:
        out["values"] = v
    return out


def solicitation_totals(conn: sqlite3.Connection, solicitation_id: int) -> list[float]:
    return [r[0] for r in conn.execute(
        "SELECT total_bid FROM v_bids_clean WHERE solicitation_id = ?", (solicitation_id,))]


def solicitation_stats(conn: sqlite3.Connection, sol_ref: str) -> dict | None:
    sol = conn.execute("SELECT * FROM v_solicitation_base WHERE sol_ref = ?", (sol_ref,)).fetchone()
    if sol is None:
        return None
    ee = sol["engineers_estimate"] if sol["ee_source"] == "ee" else None
    st = tab_stats(solicitation_totals(conn, sol["solicitation_id"]), ee, sol["gsf"])
    bids = conn.execute(
        """SELECT o.canonical_name, o.total_bid, o.price_rank, o.is_awardee, o.is_ideal, o.rank_published
           FROM v_bid_order o WHERE o.solicitation_id = ? ORDER BY o.price_rank""",
        (sol["solicitation_id"],),
    ).fetchall()
    return {
        "solicitation": dict(sol),
        "stats": st.as_dict(),
        "budget_ratio": (st.low / sol["engineers_estimate"]) if st.low and sol["engineers_estimate"]
        and sol["ee_source"] == "budget" else None,
        "bids": [dict(b) for b in bids],
    }


def agency_stats(conn: sqlite3.Connection, agency_id: str, since: str | None = None) -> dict:
    q = "SELECT solicitation_id, sol_ref, engineers_estimate, ee_source, gsf, award_basis FROM solicitations WHERE agency_id = ?"
    args: list = [agency_id]
    if since:
        q += " AND bid_open_date >= ?"
        args.append(since)
    rows = conn.execute(q, args).fetchall()
    per = []
    for r in rows:
        if r["award_basis"] != "low_bid":
            continue
        ee = r["engineers_estimate"] if r["ee_source"] == "ee" else None
        st = tab_stats(solicitation_totals(conn, r["solicitation_id"]), ee, r["gsf"])
        if st.n:
            per.append(st)
    return {
        "agency_id": agency_id,
        "tabs": len(per),
        "bidders": quartiles([s.n for s in per]),
        "gap": quartiles([s.gap for s in per if s.gap is not None]),
        "low_ee": quartiles([s.low_ee for s in per if s.low_ee is not None]),
        "cv": quartiles([s.cv for s in per if s.cv is not None]),
    }
