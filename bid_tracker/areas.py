"""Square-footage coverage: which per-project vertical tabs still have no area, and area rows whose
sol_ref matches no solicitation (a re-key left them behind, or the ref is mistyped).

area_misses.csv in the data repo records where a harvest already looked (sol_ref, searched, last_tried),
so the weekly run retries a miss only after RETRY_DAYS.
"""

from __future__ import annotations

import csv
import sqlite3
from pathlib import Path

RETRY_DAYS = 90
MISS_COLUMNS = ["sol_ref", "searched", "last_tried"]

# Jobs with one building scope. Term and rate-card contracts price per unit, not per project SF.
PER_PROJECT = """work_class = 'vertical' AND procurement_method != 'term_contract' AND award_basis != 'rate_card'
                 AND is_private = 0"""


def load_misses(path: Path) -> dict[str, dict]:
    if not path.exists():
        return {}
    with open(path, newline="", encoding="utf-8") as fh:
        return {r["sol_ref"]: r for r in csv.DictReader(fh) if r.get("sol_ref")}


def coverage(conn: sqlite3.Connection, misses_path: Path | None = None) -> dict:
    misses = load_misses(misses_path) if misses_path else {}
    tabs = conn.execute(
        f"SELECT sol_ref, project_type, bid_open_date, gsf FROM solicitations WHERE {PER_PROJECT} "
        "ORDER BY project_type, bid_open_date"
    ).fetchall()
    by_type: dict[str, dict] = {}
    for t in tabs:
        b = by_type.setdefault(t["project_type"], {"tabs": 0, "with_area": 0})
        b["tabs"] += 1
        b["with_area"] += t["gsf"] is not None
    with_area = sum(b["with_area"] for b in by_type.values())
    missing = [{"sol_ref": t["sol_ref"], "project_type": t["project_type"], "bid_open_date": t["bid_open_date"],
                "searched": (misses.get(t["sol_ref"]) or {}).get("searched"),
                "last_tried": (misses.get(t["sol_ref"]) or {}).get("last_tried")}
               for t in tabs if t["gsf"] is None]
    orphans = [dict(r) for r in conn.execute(
        """SELECT sol_ref, area_kind, sf FROM solicitation_areas
           WHERE sol_ref NOT IN (SELECT sol_ref FROM solicitations) ORDER BY sol_ref""")]
    return {
        "coverage": {"tabs": len(tabs), "with_area": with_area, "share": with_area / len(tabs) if tabs else None},
        "by_type": by_type,
        "missing": missing,
        "orphans": orphans,
    }
