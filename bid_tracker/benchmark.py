"""Segment benchmarks: what comparable public jobs went for, escalated to today's dollars.

Segment key = project_type x agency_type x region x size_band, low-bid awards only (term
contracts and not-to-exceed awards are excluded). If the full key has fewer than MIN_N tabs,
dimensions are dropped in the order size_band -> agency_type -> region and the drop is reported.
project_type is never dropped: mixing job types makes the numbers meaningless.
Low $/SF only compares tabs whose area is the same kind (roof, scope or whole building).
"""

from __future__ import annotations

import sqlite3

from bid_tracker.escalation import escalate, latest_period, series_for
from bid_tracker.stats import quartiles, solicitation_totals, tab_stats
from bid_tracker.taxonomy import area_preference, band_kind, size_band

MIN_N = 5
DROP_ORDER = ("gsf_band", "dollar_band", "agency_type", "region")
DEFAULT_SINCE = "2023-01-01"


def load_tabs(conn: sqlite3.Connection, since: str | None = DEFAULT_SINCE, to_period: str | None = None) -> list[dict]:
    q = """SELECT * FROM v_solicitation_base
           WHERE award_basis = 'low_bid' AND procurement_method != 'term_contract' AND award_is_nte = 0
             AND n_bidders > 0"""
    args: list = []
    if since:
        q += " AND bid_open_date >= ?"
        args.append(since)
    out = []
    for s in conn.execute(q + " ORDER BY bid_open_date", args).fetchall():
        ee = s["engineers_estimate"] if s["ee_source"] == "ee" else None
        st = tab_stats(solicitation_totals(conn, s["solicitation_id"]), ee, s["gsf"])
        sid = series_for(s["project_type"], s["work_class"], s["agency_type"])
        low_esc, esc = escalate(conn, st.low, s["bid_open_date"], to_period=to_period, series_id=sid)
        out.append({
            "sol_ref": s["sol_ref"], "title": s["title"], "agency_id": s["agency_id"], "agency_name": s["agency_name"],
            "project_type": s["project_type"], "work_class": s["work_class"], "agency_type": s["agency_type"],
            "region": s["region"], "county": s["county"], "gsf": s["gsf"], "area_kind": s["area_kind"],
            "gsf_band": size_band(s["gsf"], None), "dollar_band": size_band(None, st.low),
            "bid_open_date": s["bid_open_date"],
            "n": st.n, "low": st.low, "low_esc": low_esc,
            "low_psf_esc": (low_esc / s["gsf"]) if low_esc and s["gsf"] else None,
            "low_ee": st.low_ee, "gap": st.gap, "cv": st.cv, "low_median": st.low_median,
            "escalation_factor": esc.factor, "escalation_flags": esc.flags, "series_id": sid,
        })
    return out


def segment_key(project_type: str | None, agency_type: str | None, region: str | None, *,
                size: str | None = None, gsf: float | None = None, amount: float | None = None) -> dict:
    """Size compares like with like: a GSF band when floor area is known, else a dollar band."""
    key = {k: v for k, v in (("project_type", project_type), ("agency_type", agency_type), ("region", region)) if v}
    if size:
        kind = band_kind(size)
        if kind is None:
            raise ValueError(f"unknown size band {size!r}")
        key[kind] = size
    elif gsf:
        key["gsf_band"] = size_band(gsf, None)
    elif amount:
        key["dollar_band"] = size_band(None, amount)
    return key


def psf_quartiles(tabs: list[dict], kind: str | None = None, project_type: str | None = None) -> tuple[str | None, dict]:
    """Escalated low $/SF over tabs whose area is one kind: the one asked for, else the project type's
    preferred kind, else the most common kind among the tabs."""
    have = [t for t in tabs if t["low_psf_esc"] is not None and t.get("area_kind")]
    if not kind and project_type:
        kind = area_preference(project_type)[0]
    if not kind and have:
        kinds = [t["area_kind"] for t in have]
        kind = max(sorted(set(kinds)), key=kinds.count)
    return kind, quartiles([t["low_psf_esc"] for t in have if t["area_kind"] == kind])


def _match(tabs: list[dict], key: dict) -> list[dict]:
    return [t for t in tabs if all(t.get(k) == v for k, v in key.items())]


def benchmark(conn: sqlite3.Connection, *, project_type: str | None = None, agency_type: str | None = None,
              region: str | None = None, size: str | None = None, gsf: float | None = None,
              est_amount: float | None = None, since: str | None = DEFAULT_SINCE, min_n: int = MIN_N,
              to_period: str | None = None, area_kind: str | None = None) -> dict:
    tabs = load_tabs(conn, since, to_period)
    key = segment_key(project_type, agency_type, region, size=size, gsf=gsf, amount=est_amount)
    dropped: list[str] = []
    sel = _match(tabs, key)
    for dim in DROP_ORDER:
        if len(sel) >= min_n:
            break
        if dim in key:
            dropped.append(f"{dim}={key.pop(dim)}")
            sel = _match(tabs, key)
    flags = sorted({f for t in sel for f in t["escalation_flags"]})
    warnings = []
    if len(sel) < min_n:
        warnings.append(f"SMALL SAMPLE (n={len(sel)}): directional only")
    if dropped:
        warnings.append("widened segment by dropping " + ", ".join(dropped))
    periods = {t["series_id"]: latest_period(conn, t["series_id"]) for t in sel if t["series_id"]}
    psf_kind, psf = psf_quartiles(sel, area_kind, project_type)
    return {
        "key": key,
        "dropped": dropped,
        "since": since,
        "n": len(sel),
        "escalated_to": periods,
        "low_psf_esc": psf,
        "low_psf_kind": psf_kind,
        "low_esc": quartiles([t["low_esc"] for t in sel]),
        "low_ee": quartiles([t["low_ee"] for t in sel if t["low_ee"] is not None]),
        "bidders": quartiles([t["n"] for t in sel]),
        "gap": quartiles([t["gap"] for t in sel if t["gap"] is not None]),
        "cv": quartiles([t["cv"] for t in sel if t["cv"] is not None]),
        "warnings": warnings,
        "escalation_flags": flags,
        "sample": [{k: t[k] for k in ("sol_ref", "title", "bid_open_date", "n", "low", "low_esc", "gsf", "area_kind",
                                       "low_ee")}
                   for t in sel],
    }
