"""Escalate historical bid amounts to today's dollars with BLS PPI series.

    escalated = amount x I(to) / I(from)

I(p) is the latest index value at or before period p (YYYY-MM). Results carry flags when a
preliminary value is used or the requested period is past the newest data.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field

from bid_tracker import taxonomy
from bid_tracker.db import load_sources


@dataclass
class Escalation:
    factor: float | None
    series_id: str | None
    from_period: str
    to_period: str | None
    flags: list[str] = field(default_factory=list)

    def apply(self, amount: float | None) -> float | None:
        if amount is None or self.factor is None:
            return amount
        return amount * self.factor


def period_of(iso_date: str) -> str:
    return iso_date[:7]


def series_for(project_type: str | None = None, work_class: str | None = None,
               agency_type: str | None = None) -> str | None:
    """First configured series whose applies_to matches agency type, project type, then work class.
    The work class is inferred from the project type when not given."""
    series = load_sources().get("cost_index_series", [])
    if project_type and not work_class:
        work_class = next((p[1] for p in taxonomy.PROJECT_TYPES if p[0] == project_type), None)
    for key in (agency_type, project_type, work_class):
        if not key:
            continue
        for s in series:
            if key in s.get("applies_to", []):
                return s["series_id"]
    for s in series:
        if "*" in s.get("applies_to", []):
            return s["series_id"]
    return None


def index_at(conn: sqlite3.Connection, series_id: str, period: str) -> tuple[str, float, int] | None:
    row = conn.execute(
        "SELECT period, value, preliminary FROM cost_index WHERE series_id = ? AND period <= ? "
        "ORDER BY period DESC LIMIT 1",
        (series_id, period),
    ).fetchone()
    return (row["period"], row["value"], row["preliminary"]) if row else None


def latest_period(conn: sqlite3.Connection, series_id: str) -> str | None:
    row = conn.execute("SELECT MAX(period) FROM cost_index WHERE series_id = ?", (series_id,)).fetchone()
    return row[0] if row else None


def factor(conn: sqlite3.Connection, series_id: str | None, from_period: str,
           to_period: str | None = None) -> Escalation:
    esc = Escalation(None, series_id, from_period, to_period)
    if not series_id:
        esc.flags.append("no index series configured")
        return esc
    newest = latest_period(conn, series_id)
    if newest is None:
        esc.flags.append(f"no {series_id} data loaded; run refresh-index")
        return esc
    to_period = to_period or newest
    esc.to_period = to_period
    if to_period > newest:
        esc.flags.append(f"{series_id} data ends {newest}; held flat to {to_period}")
    a = index_at(conn, series_id, from_period)
    b = index_at(conn, series_id, to_period)
    if a is None:
        esc.flags.append(f"{series_id} has no data at or before {from_period}")
        return esc
    if b is None:
        esc.flags.append(f"{series_id} has no data at or before {to_period}")
        return esc
    if a[2] or b[2]:
        esc.flags.append("uses preliminary index values")
    esc.factor = b[1] / a[1]
    return esc


def escalate(conn: sqlite3.Connection, amount: float, from_date: str, *, to_period: str | None = None,
             series_id: str | None = None, project_type: str | None = None, work_class: str | None = None,
             agency_type: str | None = None) -> tuple[float | None, Escalation]:
    sid = series_id or series_for(project_type, work_class, agency_type)
    esc = factor(conn, sid, period_of(from_date), to_period)
    return esc.apply(amount), esc
