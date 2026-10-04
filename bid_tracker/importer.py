"""Load a validated package into SQLite. Idempotent: re-importing the same package adds nothing.

Dedupe rules
- Solicitations key on sol_ref. A source with higher evidence rank (official_tab > board item >
  portal notice > news > internal) replaces the row; a lower one is only recorded as an extra source.
- Bids key on (solicitation, bidder). When a package carries bids for a solicitation, they replace
  the stored bids for it (a tab is all-or-nothing).
- Bidders resolve by FL license number, then name_key, then alias; otherwise a new bidder is created.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path

from bid_tracker import taxonomy
from bid_tracker.canonical import Package, load_package, record_hash
from bid_tracker.db import upsert_agency
from bid_tracker.names import name_key
from bid_tracker.validate import Issue, has_errors, validate_package

SOL_COLUMNS = [
    "sol_ref", "agency_id", "solicitation_no", "title", "procurement_method", "award_basis", "work_class",
    "project_type", "facility_type", "county", "region", "gsf", "gsf_basis", "advertise_date", "bid_open_date",
    "engineers_estimate", "ee_source", "award_amount", "award_is_nte", "award_date", "award_status",
    "bid_bond_pct", "pp_bond_required", "sbe_goal_pct", "contract_days", "ld_per_day", "federal_funds",
    "prequal_required", "protest_filed", "source_url", "source_excerpt", "evidence_class", "retrieved_at",
    "extracted_by", "is_private", "notes",
]
# Changing only these does not make a solicitation "updated".
HASH_EXCLUDE = {"retrieved_at", "extracted_by"}


@dataclass
class ImportResult:
    run_id: int | None = None
    status: str = "ok"
    issues: list[Issue] = field(default_factory=list)
    new: int = 0
    updated: int = 0
    unchanged: int = 0
    source_only: int = 0
    bids_written: int = 0
    items_written: int = 0
    rates_written: int = 0
    pursuits: int = 0
    index_rows: int = 0
    new_refs: list[str] = field(default_factory=list)
    updated_refs: list[str] = field(default_factory=list)

    def summary(self) -> str:
        return (f"{self.new} new, {self.updated} updated, {self.unchanged} unchanged, "
                f"{self.source_only} extra-source solicitations; {self.bids_written} bids, "
                f"{self.items_written} unit-price lines, {self.rates_written} rate-card rows, "
                f"{self.pursuits} pursuits, {self.index_rows} index values")


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def known_context(conn: sqlite3.Connection) -> dict:
    bidders = {r["name_key"]: r["canonical_name"] for r in conn.execute("SELECT name_key, canonical_name FROM bidders")}
    return {
        "known_agencies": {r[0] for r in conn.execute("SELECT agency_id FROM agencies")},
        "known_sol_refs": {r[0] for r in conn.execute("SELECT sol_ref FROM solicitations")},
        "known_bidders": bidders,
    }


def resolve_bidder(conn: sqlite3.Connection, raw: str, license_no: str | None = None,
                   source_url: str | None = None) -> int:
    key = name_key(raw)
    row = None
    if license_no:
        row = conn.execute("SELECT bidder_id FROM bidders WHERE fl_license_no = ?", (license_no,)).fetchone()
    if row is None:
        row = conn.execute("SELECT bidder_id FROM bidders WHERE name_key = ?", (key,)).fetchone()
    if row is None:
        row = conn.execute("SELECT bidder_id FROM bidder_aliases WHERE alias_key = ?", (key,)).fetchone()
    if row is None:
        bidder_id = conn.execute(
            "INSERT INTO bidders(canonical_name, name_key, fl_license_no, license_source_url) VALUES (?,?,?,?)",
            (raw.strip(), key, license_no, source_url if license_no else None),
        ).lastrowid
    else:
        bidder_id = row[0]
        if license_no:
            conn.execute(
                "UPDATE bidders SET fl_license_no = coalesce(fl_license_no, ?) WHERE bidder_id = ? "
                "AND NOT EXISTS (SELECT 1 FROM bidders WHERE fl_license_no = ? AND bidder_id != ?)",
                (license_no, bidder_id, license_no, bidder_id),
            )
    conn.execute(
        "INSERT OR IGNORE INTO bidder_aliases(alias_key, bidder_id, alias_raw, source_url) VALUES (?,?,?,?)",
        (key, bidder_id, raw.strip(), source_url),
    )
    return bidder_id


def _sol_values(v: dict, conn: sqlite3.Connection) -> dict:
    out = {c: v.get(c) for c in SOL_COLUMNS if c in v}
    agency = conn.execute("SELECT region, county FROM agencies WHERE agency_id = ?", (v["agency_id"],)).fetchone()
    out["county"] = v.get("county") or (agency["county"] if agency else None)
    out["region"] = taxonomy.region_for(out["county"]) or (agency["region"] if agency else None) or "other"
    out["award_is_nte"] = v.get("award_is_nte") or 0
    out["protest_filed"] = v.get("protest_filed") or 0
    out["is_private"] = 1 if v.get("evidence_class") == "internal" else 0
    return out


def upsert_solicitation(conn: sqlite3.Connection, v: dict, run_id: int) -> tuple[int, str]:
    vals = _sol_values(v, conn)
    h = record_hash({k: x for k, x in vals.items() if k not in HASH_EXCLUDE})
    existing = conn.execute(
        "SELECT solicitation_id, evidence_class, record_hash FROM solicitations WHERE sol_ref = ?", (vals["sol_ref"],)
    ).fetchone()
    if existing is None:
        cols = list(vals) + ["record_hash", "run_id"]
        sid = conn.execute(
            f"INSERT INTO solicitations({', '.join(cols)}) VALUES ({', '.join('?' * len(cols))})",
            [vals[c] for c in vals] + [h, run_id],
        ).lastrowid
        status = "new"
    else:
        sid = existing["solicitation_id"]
        new_rank = taxonomy.EVIDENCE_RANK[vals["evidence_class"]]
        old_rank = taxonomy.EVIDENCE_RANK[existing["evidence_class"]]
        if new_rank < old_rank:
            status = "source_only"
        elif existing["record_hash"] == h:
            status = "unchanged"
        else:
            sets = ", ".join(f"{c} = ?" for c in vals)
            conn.execute(
                f"UPDATE solicitations SET {sets}, record_hash = ?, run_id = ? WHERE solicitation_id = ?",
                [vals[c] for c in vals] + [h, run_id, sid],
            )
            status = "updated"
    conn.execute(
        """INSERT INTO solicitation_sources(solicitation_id, url, excerpt, evidence_class, retrieved_at)
           VALUES (?,?,?,?,?)
           ON CONFLICT(solicitation_id, url) DO UPDATE SET excerpt = excluded.excerpt,
             evidence_class = excluded.evidence_class, retrieved_at = excluded.retrieved_at""",
        (sid, vals["source_url"], vals["source_excerpt"], vals["evidence_class"], vals["retrieved_at"]),
    )
    return sid, status


def _bid_fingerprint(conn: sqlite3.Connection, sid: int) -> list:
    return sorted(
        (r["bidder_id"], r["total_bid"], r["base_bid"], r["responsive"], r["rank_published"], r["is_awardee"])
        for r in conn.execute("SELECT * FROM bids WHERE solicitation_id = ?", (sid,))
    )


def write_bids(conn: sqlite3.Connection, sid: int, rows: list, items: list) -> tuple[int, int]:
    conn.execute("DELETE FROM bids WHERE solicitation_id = ?", (sid,))
    bid_ids: dict[str, int] = {}
    for r in rows:
        v = r.values
        bidder_id = resolve_bidder(conn, v["bidder_name_raw"], v.get("fl_license_no"), v.get("source_url"))
        bid_id = conn.execute(
            """INSERT INTO bids(solicitation_id, bidder_id, bidder_name_raw, base_bid, alternates_json, total_bid,
                 total_basis, rank_published, score_total, score_price, responsive, withdrawn, is_awardee,
                 page_ref, source_url, source_excerpt)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (sid, bidder_id, v["bidder_name_raw"], v.get("base_bid"),
             json.dumps(v["alternates_json"]) if v.get("alternates_json") is not None else None,
             v.get("total_bid"), v.get("total_basis"), v.get("rank_published"), v.get("score_total"),
             v.get("score_price"), v.get("responsive"), v.get("withdrawn") or 0, v.get("is_awardee") or 0,
             v.get("page_ref"), v["source_url"], v.get("source_excerpt")),
        ).lastrowid
        bid_ids[name_key(v["bidder_name_raw"])] = bid_id
    n_items = 0
    for r in items:
        v = r.values
        bid_id = bid_ids.get(name_key(v["bidder_name_raw"]))
        if bid_id is None:
            continue
        conn.execute(
            """INSERT INTO bid_items(bid_id, line_no, item_desc, unit, qty, unit_price, extended, item_code,
                 csi_division, is_allowance) VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (bid_id, v["line_no"], v["item_desc"], v.get("unit"), v.get("qty"), v.get("unit_price"),
             v.get("extended"), v.get("item_code"), v.get("csi_division"), v.get("is_allowance") or 0),
        )
        n_items += 1
    return len(rows), n_items


def write_rates(conn: sqlite3.Connection, sid: int, rows: list) -> int:
    conn.execute("DELETE FROM rate_cards WHERE solicitation_id = ?", (sid,))
    for r in rows:
        v = r.values
        bidder_id = resolve_bidder(conn, v["bidder_name_raw"], None, v.get("source_url"))
        conn.execute(
            """INSERT INTO rate_cards(solicitation_id, bidder_id, service, service_desc, size_min_sf, size_max_sf,
                 unit, price, after_hours_premium_pct, response_hrs, source_url, source_excerpt)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
            (sid, bidder_id, v["service"], v.get("service_desc"), v.get("size_min_sf"), v.get("size_max_sf"),
             v["unit"], v["price"], v.get("after_hours_premium_pct"), v.get("response_hrs"),
             v["source_url"], v.get("source_excerpt")),
        )
    return len(rows)


def set_awardee(conn: sqlite3.Connection, sid: int, awardee_name: str | None, source_url: str | None) -> None:
    flagged = conn.execute(
        "SELECT bidder_id FROM bids WHERE solicitation_id = ? AND is_awardee = 1 ORDER BY total_bid", (sid,)
    ).fetchall()
    bidder_id = None
    if awardee_name:
        bidder_id = resolve_bidder(conn, awardee_name, None, source_url)
        conn.execute("UPDATE bids SET is_awardee = 1 WHERE solicitation_id = ? AND bidder_id = ?", (sid, bidder_id))
    elif flagged:
        bidder_id = flagged[0]["bidder_id"]
    if bidder_id is not None:
        conn.execute("UPDATE solicitations SET awardee_bidder_id = ? WHERE solicitation_id = ?", (bidder_id, sid))


def upsert_pursuit(conn: sqlite3.Connection, v: dict) -> bool:
    row = conn.execute("SELECT solicitation_id FROM solicitations WHERE sol_ref = ?", (v["sol_ref"],)).fetchone()
    if row is None:
        return False
    cols = ["decision", "decision_date", "decision_reason", "est_direct_cost", "est_cost_pre_ohp", "bid_amount",
            "markup_pct", "result", "rank", "score_total", "score_breakdown_json", "debrief", "lessons", "estimate_dir"]
    vals = [json.dumps(v[c]) if c == "score_breakdown_json" and v.get(c) is not None else v.get(c) for c in cols]
    conn.execute(
        f"""INSERT INTO ideal_pursuits(solicitation_id, {', '.join(cols)}, updated_at)
            VALUES (?, {', '.join('?' * len(cols))}, ?)
            ON CONFLICT(solicitation_id) DO UPDATE SET
            {', '.join(f'{c} = coalesce(excluded.{c}, ideal_pursuits.{c})' for c in cols)},
            updated_at = excluded.updated_at""",
        [row[0]] + vals + [now_iso()],
    )
    return True


def upsert_index(conn: sqlite3.Connection, v: dict) -> None:
    conn.execute("INSERT OR IGNORE INTO cost_index_series(series_id) VALUES (?)", (v["series_id"],))
    conn.execute(
        """INSERT INTO cost_index(series_id, period, value, preliminary, retrieved_at) VALUES (?,?,?,?,?)
           ON CONFLICT(series_id, period) DO UPDATE SET value = excluded.value,
             preliminary = excluded.preliminary, retrieved_at = excluded.retrieved_at""",
        (v["series_id"], v["period"], v["value"], v.get("preliminary") or 0, v["retrieved_at"]),
    )


def import_package(conn: sqlite3.Connection, path: Path | str, *, feed: str = "manual", fixtures: bool = False,
                   dry_run: bool = False, today: date | None = None, pkg: Package | None = None) -> ImportResult:
    pkg = pkg or load_package(path)
    res = ImportResult()
    res.issues = validate_package(pkg, fixtures=fixtures, today=today, **known_context(conn))
    sol_rows = pkg.rows("solicitations.csv")
    rows_in = len(sol_rows) + len(pkg.rows("ideal_pursuits.csv")) + len(pkg.rows("cost_index.csv"))
    if has_errors(res.issues) or dry_run:
        res.status = "failed" if has_errors(res.issues) else "ok"
        if has_errors(res.issues) and not dry_run:
            conn.execute(
                """INSERT INTO ingest_runs(started_at, finished_at, kind, input_path, input_sha256, feed, rows_in,
                     rows_rejected, status, summary) VALUES (?,?,?,?,?,?,?,?,?,?)""",
                (now_iso(), now_iso(), "csv", str(pkg.path), pkg.sha256(), feed, rows_in, rows_in, "failed",
                 f"{sum(i.severity == 'ERROR' for i in res.issues)} validation errors"),
            )
            conn.commit()
        return res

    kind = "index" if pkg.rows("cost_index.csv") and not sol_rows else "csv"
    run_id = conn.execute(
        "INSERT INTO ingest_runs(started_at, kind, input_path, input_sha256, feed, rows_in) VALUES (?,?,?,?,?,?)",
        (now_iso(), kind, str(pkg.path), pkg.sha256(), feed, rows_in),
    ).lastrowid
    res.run_id = run_id
    try:
        for r in pkg.rows("agencies.csv"):
            upsert_agency(conn, {k: ("" if x is None else x) for k, x in r.values.items()})
        bids_by = _group(pkg.rows("bids.csv"))
        items_by = _group(pkg.rows("bid_items.csv"))
        rates_by = _group(pkg.rows("rate_cards.csv"))
        touched: set[str] = set()
        for r in sol_rows:
            v = r.values
            sid, status = upsert_solicitation(conn, v, run_id)
            touched.add(v["sol_ref"])
            changed_children = False
            if status != "source_only":
                if v["sol_ref"] in bids_by:
                    before = _bid_fingerprint(conn, sid)
                    nb, ni = write_bids(conn, sid, bids_by[v["sol_ref"]], items_by.get(v["sol_ref"], []))
                    res.bids_written += nb
                    res.items_written += ni
                    changed_children |= before != _bid_fingerprint(conn, sid)
                if v["sol_ref"] in rates_by:
                    res.rates_written += write_rates(conn, sid, rates_by[v["sol_ref"]])
                set_awardee(conn, sid, v.get("awardee_name"), v.get("source_url"))
            if status == "unchanged" and changed_children:
                status = "updated"
            if status == "new":
                res.new += 1
                res.new_refs.append(v["sol_ref"])
            elif status == "updated":
                res.updated += 1
                res.updated_refs.append(v["sol_ref"])
            elif status == "unchanged":
                res.unchanged += 1
            else:
                res.source_only += 1
        # Bids/rates for solicitations already in the DB but not in this package.
        for ref in (set(bids_by) | set(rates_by)) - touched:
            sid = conn.execute("SELECT solicitation_id FROM solicitations WHERE sol_ref = ?", (ref,)).fetchone()[0]
            if ref in bids_by:
                nb, ni = write_bids(conn, sid, bids_by[ref], items_by.get(ref, []))
                res.bids_written += nb
                res.items_written += ni
            if ref in rates_by:
                res.rates_written += write_rates(conn, sid, rates_by[ref])
            set_awardee(conn, sid, None, None)
            res.updated += 1
            res.updated_refs.append(ref)
        for r in pkg.rows("ideal_pursuits.csv"):
            res.pursuits += int(upsert_pursuit(conn, r.values))
        for r in pkg.rows("cost_index.csv"):
            upsert_index(conn, r.values)
            res.index_rows += 1
        res.status = "ok"
        conn.execute(
            """UPDATE ingest_runs SET finished_at = ?, rows_new = ?, rows_updated = ?, rows_rejected = 0,
                 status = 'ok', summary = ? WHERE run_id = ?""",
            (now_iso(), res.new, res.updated, res.summary(), run_id),
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    return res


def _group(rows: list) -> dict[str, list]:
    out: dict[str, list] = {}
    for r in rows:
        out.setdefault(r.values["sol_ref"], []).append(r)
    return out
