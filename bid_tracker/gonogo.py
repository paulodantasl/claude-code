"""Go / no-go flags from bid history plus Ideal's own limits (ideal_profile.json in the data dir).

ideal_profile.json (private, lives in the data repo):
    {"bond_limit_single": 0, "bond_limit_aggregate": 0, "largest_win": 0, "ohp_floor_pct": 0.05}
"""

from __future__ import annotations

import json
import sqlite3
import statistics
from datetime import date

from bid_tracker.benchmark import benchmark
from bid_tracker.db import data_dir
from bid_tracker.stats import agency_stats


def load_profile() -> dict:
    p = data_dir() / "ideal_profile.json"
    if p.exists():
        return json.loads(p.read_text())
    return {}


def gonogo(conn: sqlite3.Connection, *, sol_ref: str | None = None, cost: float | None = None,
           project_type: str | None = None, agency_id: str | None = None, gsf: float | None = None,
           profile: dict | None = None, today: date | None = None) -> dict:
    profile = load_profile() if profile is None else profile
    today = today or date.today()
    agency_type = region = None
    if sol_ref:
        s = conn.execute("SELECT * FROM v_solicitation_base WHERE sol_ref = ?", (sol_ref,)).fetchone()
        if s is None:
            raise ValueError(f"{sol_ref} not in DB; add it as an open solicitation first or pass --project-type/--agency")
        project_type = project_type or s["project_type"]
        agency_id = agency_id or s["agency_id"]
        gsf = gsf or s["gsf"]
    if agency_id:
        a = conn.execute("SELECT agency_type, region FROM agencies WHERE agency_id = ?", (agency_id,)).fetchone()
        if a:
            agency_type, region = a["agency_type"], a["region"]
    flags: list[dict] = []

    def flag(level: str, msg: str):
        flags.append({"level": level, "message": msg})

    ohp = profile.get("ohp_floor_pct") or 0.05
    est_bid = cost * (1 + ohp) if cost else None
    bm = benchmark(conn, project_type=project_type, agency_type=agency_type, region=region, gsf=gsf, est_amount=est_bid)
    if bm["n"] < 5:
        flag("INFO", f"insufficient history for this segment (n={bm['n']}); flags below are thin")
    p50_bidders = bm["bidders"].get("p50")
    if p50_bidders is not None and p50_bidders >= 8:
        flag("CAUTION", f"crowded field: median {p50_bidders:.0f} bidders on comparable tabs")
    p50_gap = bm["gap"].get("p50")
    if p50_gap is not None and p50_gap < 0.03:
        flag("CAUTION", f"tight pricing: median gap between low and second is {p50_gap:.1%}")

    if agency_id:
        three_years_ago = date(today.year - 3, today.month, min(today.day, 28)).isoformat()
        protests = conn.execute(
            "SELECT COUNT(*) FROM solicitations WHERE agency_id = ? AND protest_filed = 1 AND bid_open_date >= ?",
            (agency_id, three_years_ago),
        ).fetchone()[0]
        if protests >= 2:
            flag("CAUTION", f"{protests} protested awards at this agency in 3 years")
        awarded = conn.execute(
            """SELECT s.solicitation_id, s.awardee_bidder_id FROM solicitations s
               WHERE s.agency_id = ? AND s.award_basis = 'low_bid' AND s.award_status = 'awarded'
                 AND s.awardee_bidder_id IS NOT NULL""",
            (agency_id,),
        ).fetchall()
        non_low = 0
        for r in awarded:
            low = conn.execute(
                "SELECT bidder_id FROM v_bid_order WHERE solicitation_id = ? AND price_rank = 1", (r[0],)
            ).fetchone()
            if low and low[0] != r[1]:
                non_low += 1
        if len(awarded) >= 5 and non_low / len(awarded) >= 0.2:
            flag("CAUTION", f"{non_low} of {len(awarded)} low-bid awards here did not go to the low bidder")
        ag = agency_stats(conn, agency_id)
        if ag["low_ee"].get("p50") is not None and ag["low_ee"]["n"] >= 3 and ag["low_ee"]["p50"] < 0.85:
            flag("INFO", f"this agency's estimates run high: median low/EE {ag['low_ee']['p50']:.2f}")

    if est_bid:
        limit = profile.get("bond_limit_single")
        if limit and est_bid > limit:
            flag("STOP", f"estimated bid {est_bid:,.0f} exceeds the single-job bond limit {limit:,.0f}")
        largest = profile.get("largest_win")
        if largest and est_bid > 3 * largest:
            flag("CAUTION", f"estimated bid {est_bid:,.0f} is over 3x Ideal's largest win ({largest:,.0f})")
    if not profile:
        flag("INFO", "no ideal_profile.json in the data dir: bond-limit and size checks skipped")

    verdict = "STOP" if any(f["level"] == "STOP" for f in flags) else (
        "CAUTION" if any(f["level"] == "CAUTION" for f in flags) else "GO")
    return {
        "sol_ref": sol_ref, "project_type": project_type, "agency_id": agency_id,
        "agency_type": agency_type, "region": region, "estimated_bid": est_bid,
        "verdict": verdict, "flags": flags, "benchmark": {k: bm[k] for k in ("key", "n", "low_esc", "low_psf_esc", "bidders", "gap", "low_ee", "warnings")},
        "median_bidders": statistics.median([t["n"] for t in bm["sample"]]) if bm["sample"] else None,
    }
