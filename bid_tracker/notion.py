"""Notion mirror: schema DDL and a sync manifest Claude applies through the Notion MCP.

The DB is the source of truth. `export-notion` writes data/notion_out/<run>/manifest.json with one
create/update op per changed row (hash-based). Claude applies the ops with the Notion MCP, writes
acks.json ([{"db", "ref", "page_id", "hash"}]), and `notion-ack acks.json` records them in notion_map.
Relations point at Notion page URLs, so they resolve on the pass after the related page exists.
"""

from __future__ import annotations

import csv
import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from bid_tracker import taxonomy
from bid_tracker.canonical import write_csv
from bid_tracker.competitors import profiles
from bid_tracker.db import table_counts
from bid_tracker.stats import solicitation_totals, tab_stats

SCHEMA_VERSION = 1
MAP_FILE = "notion_map.csv"   # next to the DB; `rebuild` reloads it so page ids survive a fresh DB
MAP_COLUMNS = ["entity", "local_ref", "notion_page_id", "synced_hash", "synced_at"]
# Sent as null when empty, so a value that goes away (a corrected area) is cleared in Notion instead of
# lingering. The hash ignores nulls, so tabs that never had a value don't churn.
CLEARABLE = {"GSF", "Area Kind", "Area Source", "Low $/SF"}


def _opts(values, color: str = "default") -> str:
    return ", ".join(f"'{v}':{color}" for v in values)


# Property name -> Notion DDL type. Relations are added after all four databases exist.
NOTION_SCHEMA: dict[str, dict] = {
    "bid_tabs": {
        "title": "Bid Tabs",
        "description": "One row per FL public solicitation. Mirrors the private bid DB; edits here get overwritten.",
        "properties": {
            "Name": "TITLE",
            "Ref": "RICH_TEXT",
            "Agency": "SELECT()",
            "Agency Type": f"SELECT({_opts(taxonomy.AGENCY_TYPES, 'blue')})",
            "County": f"SELECT({_opts(taxonomy.REGION_COUNTIES['tampa_bay'], 'green')})",
            "Region": f"SELECT({_opts(taxonomy.REGIONS, 'purple')})",
            "Method": f"SELECT({_opts(taxonomy.PROCUREMENT_METHODS, 'gray')})",
            "Award Basis": f"SELECT({_opts(taxonomy.AWARD_BASIS, 'orange')})",
            "Work Class": f"SELECT({_opts(taxonomy.WORK_CLASSES, 'brown')})",
            "Project Type": f"SELECT({_opts(sorted(taxonomy.PROJECT_TYPE_CODES), 'yellow')})",
            "GSF": "NUMBER",
            "Area Kind": f"SELECT({_opts(taxonomy.AREA_KINDS, 'pink')})",
            "Area Source": "URL",
            "Bid Open": "DATE",
            "Bidders": "NUMBER",
            "Low Bid": "NUMBER FORMAT 'dollar'",
            "Second Bid": "NUMBER FORMAT 'dollar'",
            "Gap": "NUMBER FORMAT 'percent'",
            "Engineer's Estimate": "NUMBER FORMAT 'dollar'",
            "EE Source": f"SELECT({_opts(taxonomy.EE_SOURCES, 'gray')})",
            "Low/EE": "NUMBER FORMAT 'percent'",
            "Low $/SF": "NUMBER FORMAT 'dollar'",
            "Award": "NUMBER FORMAT 'dollar'",
            "Awardee": "RICH_TEXT",
            "Award Date": "DATE",
            "Status": f"SELECT({_opts(taxonomy.AWARD_STATUS, 'blue')})",
            "Evidence": f"SELECT({_opts(taxonomy.EVIDENCE_CLASSES, 'green')})",
            "Date Basis": f"SELECT({_opts(taxonomy.DATE_BASIS, 'gray')})",
            "Source URL": "URL",
            "Excerpt": "RICH_TEXT",
            "Retrieved": "DATE",
            "Ideal Bid": "CHECKBOX",
        },
        "relations": {"Bidders on Tab": "bidders", "Pursuit": "pursuits"},
    },
    "bidders": {
        "title": "Bidders",
        "description": "Every firm seen on a FL public bid tab, with pricing behaviour. Mirrors the private bid DB.",
        "properties": {
            "Name": "TITLE",
            "Ref": "RICH_TEXT",
            "FL License": "RICH_TEXT",
            "HQ County": "SELECT()",
            "Bids": "NUMBER",
            "Wins": "NUMBER",
            "Low Bids": "NUMBER",
            "Win Rate": "NUMBER FORMAT 'percent'",
            "Median Above Low": "NUMBER FORMAT 'percent'",
            "Median Bid/EE": "NUMBER FORMAT 'percent'",
            "Agencies": "MULTI_SELECT()",
            "Counties": "MULTI_SELECT()",
            "Project Types": "MULTI_SELECT()",
            "Last Bid": "DATE",
            "Is Ideal": "CHECKBOX",
        },
        "relations": {},
    },
    "pursuits": {
        "title": "Ideal Pursuits",
        "description": "Ideal's own public bids: go/no-go, cost, bid, markup, result, debrief. Team-internal.",
        "properties": {
            "Name": "TITLE",
            "Ref": "RICH_TEXT",
            "Decision": f"SELECT({_opts(taxonomy.PURSUIT_DECISIONS, 'blue')})",
            "Decision Date": "DATE",
            "Cost Pre-OH&P": "NUMBER FORMAT 'dollar'",
            "Our Bid": "NUMBER FORMAT 'dollar'",
            "Markup": "NUMBER FORMAT 'percent'",
            "Low Bid": "NUMBER FORMAT 'dollar'",
            "Result": f"SELECT({_opts(taxonomy.PURSUIT_RESULTS, 'orange')})",
            "Rank": "NUMBER",
            "Score": "NUMBER",
            "Debrief": "RICH_TEXT",
            "Lessons": "RICH_TEXT",
        },
        "relations": {"Bid Tab": "bid_tabs"},
    },
    "updates": {
        "title": "Bid Pricing Updates",
        "description": "One row per harvest / sync run.",
        "properties": {
            "Name": "TITLE",
            "Date": "DATE",
            "Feed": f"SELECT({_opts(taxonomy.FEEDS, 'blue')})",
            "New rows": "NUMBER",
            "Updated rows": "NUMBER",
            "DB total": "NUMBER",
            "Status": "STATUS",
            "Summary": "RICH_TEXT",
        },
        "relations": {},
    },
}


def ddl(db: str) -> str:
    props = NOTION_SCHEMA[db]["properties"]
    cols = []
    for name, kind in props.items():
        # Options for open-ended selects (agency, county...) are created as values arrive.
        kind = kind.replace("SELECT()", "SELECT")
        cols.append(f'"{name}" {kind}')
    return "CREATE TABLE (" + ", ".join(cols) + ")"


def _date(props: dict, name: str, value: str | None) -> None:
    if value:
        props[f"date:{name}:start"] = value[:10]
        props[f"date:{name}:is_datetime"] = 0


def _yes(v) -> str:
    return "__YES__" if v else "__NO__"


def _h(obj) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, default=str).encode()).hexdigest()


_MD_SPECIAL = set("\\*~`$[]<>{}|^")


def md_escape(text) -> str:
    """Escape Notion-flavored Markdown specials so data renders literally."""
    return "".join("\\" + ch if ch in _MD_SPECIAL else ch for ch in str(text))


def _table(headers: list[str], rows: list[list], money: tuple[int, ...] = ()) -> str:
    """money = column indexes shown as dollars; other numbers print plain."""
    def cell(i, v):
        if v is None:
            return ""
        if i in money and isinstance(v, (int, float)):
            return md_escape(f"${v:,.2f}")
        if isinstance(v, float):
            return md_escape(f"{v:,.0f}" if v == int(v) else f"{v:,.2f}")
        return md_escape(v)

    out = ['<table header-row="true">', "<tr>" + "".join(f"<td>{h}</td>" for h in headers) + "</tr>"]
    out += ["<tr>" + "".join(f"<td>{cell(i, v)}</td>" for i, v in enumerate(r)) + "</tr>" for r in rows]
    out.append("</table>")
    return "\n".join(out)


def bid_tab_payload(conn: sqlite3.Connection, s: sqlite3.Row) -> tuple[dict, str, list[str]]:
    ee = s["engineers_estimate"] if s["ee_source"] == "ee" else None
    st = tab_stats(solicitation_totals(conn, s["solicitation_id"]), ee, s["gsf"])
    bids = conn.execute(
        """SELECT b.*, br.canonical_name, br.name_key, br.is_ideal FROM bids b JOIN bidders br USING (bidder_id)
           WHERE b.solicitation_id = ? ORDER BY (b.total_bid IS NULL), b.total_bid, b.rank_published""",
        (s["solicitation_id"],),
    ).fetchall()
    area = conn.execute("SELECT * FROM solicitation_areas WHERE sol_ref = ? AND area_kind = ?",
                        (s["sol_ref"], s["area_kind"])).fetchone() if s["area_kind"] else None
    props = {
        "Name": f"{s['agency_name']} {s['solicitation_no']} — {s['title']}"[:200],
        "Ref": s["sol_ref"], "Agency": s["agency_name"], "Agency Type": s["agency_type"], "County": s["county"],
        "Region": s["region"], "Method": s["procurement_method"], "Award Basis": s["award_basis"],
        "Work Class": s["work_class"], "Project Type": s["project_type"], "GSF": s["gsf"],
        "Area Kind": s["area_kind"], "Area Source": area["source_url"] if area else None,
        "Bidders": st.n or None, "Low Bid": st.low, "Second Bid": st.second, "Gap": st.gap,
        "Engineer's Estimate": s["engineers_estimate"], "EE Source": s["ee_source"], "Low/EE": st.low_ee,
        "Low $/SF": st.low_psf, "Award": s["award_amount"],
        "Awardee": "; ".join(b["canonical_name"] for b in bids if b["is_awardee"]) or s["awardee_name"],
        "Status": s["award_status"], "Evidence": s["evidence_class"], "Date Basis": s["date_basis"],
        "Source URL": s["source_url"],
        "Excerpt": (s["source_excerpt"] or "")[:1900],
        "Ideal Bid": _yes(any(b["is_ideal"] for b in bids)),
    }
    _date(props, "Bid Open", s["bid_open_date"])
    _date(props, "Award Date", s["award_date"])
    _date(props, "Retrieved", s["retrieved_at"])
    props = {k: v for k, v in props.items() if v is not None or k in CLEARABLE}
    # The quoted excerpt lives in the Excerpt property; the body carries the tables.
    body = [f"**Source:** [{s['evidence_class']}]({s['source_url']}) · retrieved {s['retrieved_at']}"]
    for a in conn.execute("SELECT * FROM solicitation_areas WHERE sol_ref = ? ORDER BY area_kind", (s["sol_ref"],)):
        page = f", {md_escape(a['source_page'])}" if a["source_page"] else ""
        used = " · used for $/SF" if a["area_kind"] == s["area_kind"] else ""
        body.append(f"**Area:** {a['sf']:,.0f} SF {a['area_kind'].replace('_', ' ')} ({a['basis']}){used} · "
                    f"[source]({a['source_url']}){page}")
    if bids:
        scored = any(b["score_total"] is not None for b in bids)
        body.append("### Bids")
        body.append(_table(["Bidder", "Base", "Total", "Rank"] + (["Score"] if scored else []) + ["Responsive", "Awardee"],
                           [[b["canonical_name"], b["base_bid"], b["total_bid"], b["rank_published"]]
                            + ([b["score_total"]] if scored else [])
                            + [{1: "yes", 0: "no"}.get(b["responsive"], ""), "yes" if b["is_awardee"] else ""]
                            for b in bids], money=(1, 2)))
    items = conn.execute(
        """SELECT br.canonical_name, i.line_no, i.item_desc, i.unit, i.qty, i.unit_price, i.extended
           FROM bid_items i JOIN bids b USING (bid_id) JOIN bidders br ON br.bidder_id = b.bidder_id
           WHERE b.solicitation_id = ? ORDER BY br.canonical_name, i.line_no LIMIT 80""",
        (s["solicitation_id"],),
    ).fetchall()
    if items:
        body.append("### Unit prices")
        body.append(_table(["Bidder", "Line", "Item", "Unit", "Qty", "Unit price", "Extended"], [list(i) for i in items],
                           money=(5, 6)))
    rates = conn.execute(
        """SELECT br.canonical_name, r.service, r.size_min_sf, r.size_max_sf, r.unit, r.price, r.after_hours_premium_pct
           FROM rate_cards r JOIN bidders br USING (bidder_id) WHERE r.solicitation_id = ?
           ORDER BY br.canonical_name, r.service, r.size_min_sf""",
        (s["solicitation_id"],),
    ).fetchall()
    if rates:
        body.append("### Rate card")
        body.append(_table(["Bidder", "Service", "Min SF", "Max SF", "Unit", "Price", "After-hours %"],
                           [[r[0], r[1], r[2], r[3], r[4], r[5], r[6]] for r in rates], money=(5,)))
    body.append("*Mirrors the private bid DB. Edits here get overwritten on the next sync.*")
    bidder_refs = {b["name_key"] for b in bids}
    awardee = conn.execute("SELECT name_key FROM bidders WHERE bidder_id = ?", (s["awardee_bidder_id"],)).fetchone()
    if awardee:
        bidder_refs.add(awardee[0])
    bidder_refs = sorted(bidder_refs)
    return props, "\n\n".join(body), bidder_refs


def bidder_payload(p: dict, conn: sqlite3.Connection) -> dict:
    b = conn.execute("SELECT * FROM bidders WHERE bidder_id = ?", (p["bidder_id"],)).fetchone()
    props = {
        "Name": b["canonical_name"], "Ref": b["name_key"], "FL License": b["fl_license_no"],
        "HQ County": b["hq_county"], "Bids": p["bids"], "Wins": p["wins"], "Low Bids": p["low_bids"],
        "Win Rate": p["win_rate"], "Median Above Low": p["pct_above_low"], "Median Bid/EE": p["bid_ee"],
        "Agencies": json.dumps(p["agencies"]), "Counties": json.dumps(p["counties"]),
        "Project Types": json.dumps(p["project_types"]), "Is Ideal": _yes(b["is_ideal"]),
    }
    _date(props, "Last Bid", p["last_bid"])
    return {k: v for k, v in props.items() if v is not None}


def _mapped(conn: sqlite3.Connection, entity: str) -> dict[str, sqlite3.Row]:
    return {r["local_ref"]: r for r in conn.execute("SELECT * FROM notion_map WHERE entity = ?", (entity,))}


def _page_url(page_id: str | None) -> str | None:
    return f"https://www.notion.so/{page_id.replace('-', '')}" if page_id else None


def export(conn: sqlite3.Connection, out_root: Path, *, all_rows: bool = False, feed: str = "manual") -> Path:
    run = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_dir = Path(out_root) / run
    ops: list[dict] = []
    maps = {e: _mapped(conn, e) for e in ("bid_tab", "bidder", "pursuit")}

    def add(db: str, entity: str, ref: str, props: dict, body: str | None = None, relations: dict | None = None):
        rel_resolved, pending = {}, {}
        for name, (target, refs) in (relations or {}).items():
            urls = [_page_url(maps[target][r]["notion_page_id"]) for r in refs
                    if r in maps[target] and maps[target][r]["notion_page_id"]]
            missing = [r for r in refs if r not in maps[target] or not maps[target][r]["notion_page_id"]]
            rel_resolved[name] = urls
            if missing:
                pending[name] = missing
        payload = {"properties": props, "content": body, "relations": rel_resolved}
        h = _h({**payload, "properties": {k: v for k, v in props.items() if v is not None}})
        known = maps[entity].get(ref)
        if known and known["synced_hash"] == h and not all_rows:
            return
        op = {"db": db, "entity": entity, "ref": ref, "op": "update" if known and known["notion_page_id"] else "create",
              "page_id": known["notion_page_id"] if known else None, "hash": h, **payload}
        if pending:
            op["pending_relations"] = pending
        ops.append(op)

    # Bidders first so tab relations can resolve on the next pass. Firms seen only on rate-card or
    # qualifications awards get a page too (no pricing stats), so every tab relation can resolve.
    profiled = set()
    for p in profiles(conn, top=0, include_ideal=True):
        props = bidder_payload(p, conn)
        add("bidders", "bidder", props["Ref"], props)
        profiled.add(p["bidder_id"])
    for b in conn.execute(
        """SELECT * FROM bidders WHERE bidder_id IN (SELECT bidder_id FROM bids UNION SELECT bidder_id FROM rate_cards
             UNION SELECT awardee_bidder_id FROM solicitations WHERE awardee_bidder_id IS NOT NULL)
           ORDER BY canonical_name"""
    ).fetchall():
        if b["bidder_id"] in profiled:
            continue
        props = {"Name": b["canonical_name"], "Ref": b["name_key"], "FL License": b["fl_license_no"],
                 "HQ County": b["hq_county"], "Is Ideal": _yes(b["is_ideal"]),
                 "Bids": conn.execute("SELECT COUNT(*) FROM bids WHERE bidder_id = ?", (b["bidder_id"],)).fetchone()[0],
                 "Wins": conn.execute("SELECT COUNT(*) FROM bids WHERE bidder_id = ? AND is_awardee = 1",
                                      (b["bidder_id"],)).fetchone()[0]}
        add("bidders", "bidder", b["name_key"], {k: v for k, v in props.items() if v is not None})
    for s in conn.execute("SELECT * FROM v_solicitation_base ORDER BY bid_open_date").fetchall():
        props, body, bidder_refs = bid_tab_payload(conn, s)
        rel = {"Bidders on Tab": ("bidder", bidder_refs)}
        add("bid_tabs", "bid_tab", s["sol_ref"], props, body, rel)
    for p in conn.execute(
        """SELECT p.*, s.sol_ref, s.title, s.solicitation_id AS sid FROM ideal_pursuits p
           JOIN solicitations s USING (solicitation_id)"""
    ).fetchall():
        low = tab_stats(solicitation_totals(conn, p["sid"])).low
        props = {
            "Name": f"{p['sol_ref']} — {p['title']}"[:200], "Ref": p["sol_ref"], "Decision": p["decision"],
            "Cost Pre-OH&P": p["est_cost_pre_ohp"], "Our Bid": p["bid_amount"], "Markup": p["markup_pct"],
            "Low Bid": low, "Result": p["result"], "Rank": p["rank"], "Score": p["score_total"],
            "Debrief": (p["debrief"] or "")[:1900] or None, "Lessons": (p["lessons"] or "")[:1900] or None,
        }
        _date(props, "Decision Date", p["decision_date"])
        props = {k: v for k, v in props.items() if v is not None}
        add("pursuits", "pursuit", p["sol_ref"], props, None, {"Bid Tab": ("bid_tab", [p["sol_ref"]])})

    counts = table_counts(conn)
    new_tabs = sum(1 for o in ops if o["db"] == "bid_tabs" and o["op"] == "create")
    upd_tabs = sum(1 for o in ops if o["db"] == "bid_tabs" and o["op"] == "update")
    if new_tabs or upd_tabs:
        last = conn.execute("SELECT summary FROM ingest_runs WHERE status = 'ok' ORDER BY run_id DESC LIMIT 1").fetchone()
        ops.append({
            "db": "updates", "entity": "update", "ref": run, "op": "create", "page_id": None,
            "properties": {
                "Name": f"Bid pricing sync {run[:8]}", "Feed": feed, "New rows": new_tabs, "Updated rows": upd_tabs,
                "DB total": counts["solicitations"], "Status": "Done",
                "Summary": (f"{new_tabs} new and {upd_tabs} updated bid tabs; DB holds {counts['solicitations']} "
                            f"solicitations, {counts['bids']} bids, {counts['bidders']} bidders. "
                            f"Last import: {last[0] if last else 'n/a'}")[:1900],
                "date:Date:start": datetime.now(timezone.utc).date().isoformat(), "date:Date:is_datetime": 0,
            },
            "content": None, "relations": {}, "hash": None,
        })
    manifest = {"schema_version": SCHEMA_VERSION, "run": run, "counts": counts,
                "options": required_options(ops), "ops": ops}
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, default=str))
    return out_dir / "manifest.json"


def required_options(ops: list[dict]) -> dict[str, dict[str, list[str]]]:
    """Select / multi-select values each database needs. Notion refuses a value that is not already an
    option, so the sync adds these (ALTER COLUMN ... SET SELECT(...)) before writing pages."""
    need: dict[str, dict[str, set]] = {}
    for op in ops:
        props = NOTION_SCHEMA[op["db"]]["properties"]
        for name, kind in props.items():
            if "SELECT" not in kind or name not in op["properties"]:
                continue
            value = op["properties"][name]
            values = json.loads(value) if kind.startswith("MULTI_SELECT") else [value]
            need.setdefault(op["db"], {}).setdefault(name, set()).update(v for v in values if v)
    return {db: {name: sorted(v) for name, v in props.items()} for db, props in need.items()}


def ack(conn: sqlite3.Connection, acks: list[dict]) -> int:
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    n = 0
    for a in acks:
        if a.get("entity") == "update" or a.get("db") == "updates":
            continue
        entity = a.get("entity") or {"bid_tabs": "bid_tab", "bidders": "bidder", "pursuits": "pursuit"}[a["db"]]
        conn.execute(
            """INSERT INTO notion_map(entity, local_ref, notion_page_id, synced_hash, synced_at) VALUES (?,?,?,?,?)
               ON CONFLICT(entity, local_ref) DO UPDATE SET notion_page_id = excluded.notion_page_id,
                 synced_hash = excluded.synced_hash, synced_at = excluded.synced_at""",
            (entity, a["ref"], a["page_id"], a.get("hash"), now),
        )
        n += 1
    conn.execute("UPDATE ingest_runs SET notion_synced_at = ? WHERE notion_synced_at IS NULL", (now,))
    conn.commit()
    return n


def save_map(conn: sqlite3.Connection, path: Path) -> int:
    """Write notion_map to CSV. Without it a rebuilt DB re-creates every Notion page as a duplicate."""
    rows = [dict(r) for r in conn.execute("SELECT * FROM notion_map ORDER BY entity, local_ref")]
    write_csv(path, MAP_COLUMNS, rows)
    return len(rows)


def load_map(conn: sqlite3.Connection, path: Path) -> int:
    if not path.exists():
        return 0
    with open(path, newline="", encoding="utf-8") as fh:
        rows = [tuple(r.get(c) or None for c in MAP_COLUMNS) for r in csv.DictReader(fh)]
    conn.executemany(
        f"INSERT OR REPLACE INTO notion_map({', '.join(MAP_COLUMNS)}) VALUES ({', '.join('?' * len(MAP_COLUMNS))})",
        rows)
    conn.commit()
    return len(rows)


def orphan_bidders(conn: sqlite3.Connection) -> list[dict]:
    """Mapped bidder pages for firms that were merged away: the ref no longer names a bidder with any
    bid, rate card or award, and it is a recorded alias (private/bidder_aliases.csv). Never derive this
    from a manifest: unchanged bidders are absent from manifests but very much alive."""
    return [dict(r) for r in conn.execute(
        """SELECT m.local_ref, m.notion_page_id FROM notion_map m
           WHERE m.entity = 'bidder'
             AND m.local_ref NOT IN (
                 SELECT b.name_key FROM bidders b
                 WHERE EXISTS (SELECT 1 FROM bids WHERE bidder_id = b.bidder_id)
                    OR EXISTS (SELECT 1 FROM rate_cards WHERE bidder_id = b.bidder_id)
                    OR EXISTS (SELECT 1 FROM solicitations WHERE awardee_bidder_id = b.bidder_id))
             AND m.local_ref IN (SELECT alias_key FROM bidder_aliases)
           ORDER BY m.local_ref""")]


def forget(conn: sqlite3.Connection, entity: str, refs: list[str]) -> int:
    n = 0
    for ref in refs:
        n += conn.execute("DELETE FROM notion_map WHERE entity = ? AND local_ref = ?", (entity, ref)).rowcount
    conn.commit()
    return n
