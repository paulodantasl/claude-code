"""Competitive-bid positioning (Friedman-style) and best-value price-score sensitivity.

Low-bid mode
------------
Each historical competitor bid becomes a ratio r against a reference R of its tab:
    ee     r = bid / EE                  (default; tabs with a true engineer's estimate)
    median r = bid / median(tab)         (no EE published; you supply the expected median)
    own    r = bid / Ideal's cost        (true Friedman; needs >= 8 Ideal pursuits with tabs)
ln r is fitted with a normal (mu, sigma). For our cost C and this job's reference R, x = C / R.
At markup m our bid is B = C(1 + m), and one competitor bids above us with probability
    P1(m)   = 1 - Phi((ln(x(1 + m)) - mu) / sigma)
Against k competitors drawn from the segment's empirical competitor-count distribution p(k):
    P_win(m) = sum_k p(k) * P1(m)^k
    E[profit](m) = P_win(m) * m * C - bid_cost
The empirical P1 (share of historical ratios above our ratio) is printed beside the fit.

Best-value mode
---------------
Price points for bid B against the lowest price L: ratio PP = W * L / B; linear PP = W * max(0, 1 - (B - L) / L).
If a competitor leads us by D non-price points, we need PP(B) - PP(Pc) >= D. Under the ratio formula the
best we can do while low is W * (1 - B / Pc), so the break-even bid is B* = Pc * (1 - D / W). If B* is below
our cost, price cannot close the gap — fix the proposal, not the number.
"""

from __future__ import annotations

import math
import sqlite3
import statistics
from collections import Counter
from dataclasses import dataclass, field

from bid_tracker.benchmark import DEFAULT_SINCE, DROP_ORDER, segment_key
from bid_tracker.taxonomy import size_band

MIN_RATIOS = 10
WARN_RATIOS = 30
MIN_OWN_PURSUITS = 8

CAVEATS = [
    "Competitors are treated as independent draws from past behaviour; real fields move together with the market.",
    "Assumes the past is like now (escalation corrects price level, not competitive pressure or backlog).",
    "Ignores error in our own estimate: winning often means we underestimated (winner's curse).",
    "This informs OH&P only. It never lowers the bond, insurance, or general-conditions floors.",
]


def phi(z: float) -> float:
    return 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))


def fit_lognormal(ratios: list[float]) -> tuple[float, float]:
    logs = [math.log(r) for r in ratios if r > 0]
    return statistics.fmean(logs), statistics.stdev(logs)


def p_one_above(t: float, mu: float, sigma: float) -> float:
    """Probability one competitor's ratio exceeds t."""
    if sigma <= 0:
        return 1.0 if math.log(t) < mu else 0.0
    return 1.0 - phi((math.log(t) - mu) / sigma)


def p_win(p1: float, k_dist: dict[int, float]) -> float:
    return sum(p * (p1 ** k) for k, p in k_dist.items())


def markup_grid(spec: str = "0:0.20:0.01") -> list[float]:
    lo, hi, step = (float(x) for x in spec.split(":"))
    n = int(round((hi - lo) / step))
    return [round(lo + i * step, 6) for i in range(n + 1)]


@dataclass
class RatioSet:
    ratios: list[float] = field(default_factory=list)
    comp_counts: list[int] = field(default_factory=list)
    tabs: int = 0
    key: dict = field(default_factory=dict)
    dropped: list[str] = field(default_factory=list)


def _segment_tabs(conn: sqlite3.Connection, key: dict, since: str | None) -> list[sqlite3.Row]:
    q = """SELECT * FROM v_solicitation_base WHERE award_basis = 'low_bid' AND n_bidders > 0
           AND procurement_method != 'term_contract'"""
    args: list = []
    if since:
        q += " AND bid_open_date >= ?"
        args.append(since)
    for col in ("project_type", "agency_type", "region"):
        if col in key:
            q += f" AND {col} = ?"
            args.append(key[col])
    rows = conn.execute(q, args).fetchall()
    if "gsf_band" in key:
        rows = [r for r in rows if size_band(r["gsf"], None) == key["gsf_band"]]
    if "dollar_band" in key:
        rows = [r for r in rows if size_band(None, r["low_bid"]) == key["dollar_band"]]
    return rows


def _ratios_for(conn: sqlite3.Connection, tabs: list[sqlite3.Row], mode: str) -> RatioSet:
    rs = RatioSet()
    own_cost = {}
    if mode == "own":
        own_cost = {r[0]: r[1] for r in conn.execute(
            "SELECT solicitation_id, est_cost_pre_ohp FROM ideal_pursuits WHERE est_cost_pre_ohp > 0")}
    for t in tabs:
        bids = conn.execute(
            "SELECT total_bid, is_ideal FROM v_bids_clean WHERE solicitation_id = ?", (t["solicitation_id"],)
        ).fetchall()
        comp = [b["total_bid"] for b in bids if not b["is_ideal"]]
        if not comp:
            continue
        if mode == "ee":
            if t["ee_source"] != "ee" or not t["engineers_estimate"]:
                continue
            ref = t["engineers_estimate"]
        elif mode == "median":
            ref = statistics.median([b["total_bid"] for b in bids])
        else:
            ref = own_cost.get(t["solicitation_id"])
            if not ref:
                continue
        rs.ratios.extend(b / ref for b in comp)
        rs.comp_counts.append(len(comp))
        rs.tabs += 1
    return rs


def competitor_ratios(conn: sqlite3.Connection, mode: str, *, project_type: str | None, agency_type: str | None = None,
                      region: str | None = None, gsf: float | None = None, amount: float | None = None,
                      since: str | None = DEFAULT_SINCE) -> RatioSet:
    key = segment_key(project_type, agency_type, region, gsf=gsf, amount=amount)
    dropped: list[str] = []
    rs = _ratios_for(conn, _segment_tabs(conn, key, since), mode)
    for dim in DROP_ORDER:
        if len(rs.ratios) >= WARN_RATIOS:
            break
        if dim in key:
            dropped.append(f"{dim}={key.pop(dim)}")
            rs = _ratios_for(conn, _segment_tabs(conn, key, since), mode)
    rs.key, rs.dropped = key, dropped
    return rs


def position(conn: sqlite3.Connection, *, cost: float, ee: float | None = None, expected_median: float | None = None,
             project_type: str | None = None, agency_type: str | None = None, region: str | None = None,
             gsf: float | None = None, bidders: int | None = None, markups: list[float] | None = None,
             bid_cost: float = 0.0, mode: str | None = None, since: str | None = DEFAULT_SINCE) -> dict:
    markups = markups or markup_grid()
    if mode is None:
        n_own = conn.execute(
            """SELECT COUNT(*) FROM ideal_pursuits p WHERE est_cost_pre_ohp > 0
               AND EXISTS (SELECT 1 FROM v_bids_clean c WHERE c.solicitation_id = p.solicitation_id AND c.is_ideal = 0)"""
        ).fetchone()[0]
        mode = "own" if n_own >= MIN_OWN_PURSUITS else ("ee" if ee else "median")
    if mode == "ee" and not ee:
        raise ValueError("ee mode needs --ee (this job's engineer's estimate)")
    if mode == "median" and not expected_median:
        raise ValueError("median mode needs --expected-median (your read of where the field will land)")
    reference = {"ee": ee, "median": expected_median, "own": cost}[mode]
    rs = competitor_ratios(conn, mode, project_type=project_type, agency_type=agency_type, region=region,
                           gsf=gsf, amount=None if mode == "own" else reference, since=since)
    result = {
        "mode": mode, "cost": cost, "reference": reference, "x": cost / reference,
        "segment": rs.key, "dropped": rs.dropped, "n_ratios": len(rs.ratios), "n_tabs": rs.tabs,
        "caveats": CAVEATS, "flags": [],
    }
    if len(rs.ratios) < MIN_RATIOS:
        result["refused"] = (f"only {len(rs.ratios)} competitor bids in this segment (need {MIN_RATIOS}); "
                             "use benchmark ranges and judgment instead")
        return result
    if len(rs.ratios) < WARN_RATIOS:
        result["flags"].append(f"thin history ({len(rs.ratios)} competitor bids): treat P(win) as rough")
    if rs.dropped:
        result["flags"].append("segment widened: dropped " + ", ".join(rs.dropped))
    mu, sigma = fit_lognormal(rs.ratios)
    if bidders:
        k_dist = {max(bidders - 1, 0): 1.0}
    else:
        counts = Counter(rs.comp_counts)
        total = sum(counts.values())
        k_dist = {k: c / total for k, c in counts.items()}
    rows = []
    x = result["x"]
    for m in markups:
        t = x * (1 + m)
        p1 = p_one_above(t, mu, sigma)
        p1_emp = sum(1 for r in rs.ratios if r > t) / len(rs.ratios)
        pw = p_win(p1, k_dist)
        rows.append({
            "markup": m, "bid": cost * (1 + m), "bid_ref": t,
            "p1_fit": p1, "p1_empirical": p1_emp, "p_win": pw,
            "expected_profit": pw * m * cost - bid_cost,
        })
    best = max(rows, key=lambda r: r["expected_profit"])
    result.update(mu=mu, sigma=sigma, k_dist=k_dist, table=rows, m_star=best["markup"], best=best)
    return result


def price_points(bid: float, low: float, weight: float, formula: str = "ratio") -> float:
    if formula == "ratio":
        return weight * min(1.0, low / bid)
    if formula == "linear":
        return weight * max(0.0, 1.0 - (bid - low) / low)
    raise ValueError(f"unknown price formula {formula!r}")


def best_value(*, cost: float, competitor_price: float, weight: float, nonprice_gap: float = 0.0,
               formula: str = "ratio", markups: list[float] | None = None) -> dict:
    markups = markups or markup_grid()
    rows = []
    for m in markups:
        b = cost * (1 + m)
        low = min(b, competitor_price)
        ours = price_points(b, low, weight, formula)
        theirs = price_points(competitor_price, low, weight, formula)
        rows.append({"markup": m, "bid": b, "our_points": ours, "their_points": theirs,
                     "net": ours - theirs - nonprice_gap})
    # Largest bid that still nets zero against the competitor's non-price lead.
    if not weight:
        breakeven = None
    elif formula == "ratio":
        breakeven = competitor_price * (1 - nonprice_gap / weight)       # W(1 - B/Pc) = D
    else:
        breakeven = competitor_price / (1 + nonprice_gap / weight)       # W(Pc - B)/B = D
    result = {
        "cost": cost, "competitor_price": competitor_price, "weight": weight, "formula": formula,
        "nonprice_gap": nonprice_gap, "breakeven_bid": breakeven, "table": rows, "flags": [],
    }
    if breakeven is not None and breakeven < cost:
        result["flags"].append(
            f"price cannot close the gap: you would need to bid {breakeven:,.0f}, below your cost {cost:,.0f}. "
            "Win the non-price points instead."
        )
    elif breakeven is not None:
        result["max_markup_to_close_gap"] = breakeven / cost - 1
    return result
