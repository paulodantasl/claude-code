"""Socrata (SODA) adapter: pull an open-data procurement dataset into a solicitations package.

Configured per dataset in sources.toml ([[socrata]] blocks). Most FL agencies publish awards as
PDFs, so this matters mainly for statewide expansion. Rows still go through the validator:
the source excerpt is the raw record, so E-NOSRC holds.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from urllib.parse import urlencode

from bid_tracker.adapters.http import Fetch, get_json, urllib_fetch
from bid_tracker.canonical import SPECS, make_sol_ref, write_csv
from bid_tracker.db import load_sources

DEFAULTS = {
    "procurement_method": "ITB", "award_basis": "low_bid", "award_status": "awarded",
    "evidence_class": "portal_award_notice", "extracted_by": "socrata-adapter",
}


def source_config(name: str) -> dict:
    for s in load_sources().get("socrata", []):
        if s["name"] == name:
            return s
    raise KeyError(f"no [[socrata]] source named {name!r} in sources.toml")


def query_url(cfg: dict, since: str | None, limit: int = 5000) -> str:
    params = {"$limit": str(limit)}
    where = [cfg["where"]] if cfg.get("where") else []
    date_col = cfg.get("columns", {}).get("award_date")
    if since and date_col:
        where.append(f"{date_col} >= '{since}'")
    if where:
        params["$where"] = " AND ".join(where)
    return f"https://{cfg['domain']}/resource/{cfg['dataset']}.json?{urlencode(params)}"


def to_rows(records: list[dict], cfg: dict, today: date) -> list[dict]:
    cols = cfg["columns"]
    out = []
    for rec in records:
        row = {k: rec.get(v, "") for k, v in cols.items()}
        row.update({k: v for k, v in DEFAULTS.items() if not row.get(k)})
        row.update({k: v for k, v in cfg.get("defaults", {}).items() if not row.get(k)})
        row["agency_id"] = cfg["agency_id"]
        row["sol_ref"] = make_sol_ref(cfg["agency_id"], row.get("solicitation_no", ""))
        row["bid_open_date"] = row.get("bid_open_date") or row.get("award_date", "")
        row["source_url"] = f"https://{cfg['domain']}/d/{cfg['dataset']}"
        row["source_excerpt"] = json.dumps(rec, sort_keys=True)[:1500]
        row["retrieved_at"] = today.isoformat()
        out.append(row)
    return out


def build_package(name: str, out_dir: Path, *, since: str | None = None, fetch: Fetch = urllib_fetch,
                  today: date | None = None) -> tuple[Path, int]:
    cfg = source_config(name)
    records = get_json(query_url(cfg, since), fetch=fetch)
    rows = to_rows(records, cfg, today or date.today())
    write_csv(out_dir / "solicitations.csv", list(SPECS["solicitations.csv"]), rows)
    return out_dir, len(rows)
