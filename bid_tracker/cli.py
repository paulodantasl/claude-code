"""python3 -m bid_tracker <command> — see README.md for the full workflow."""

from __future__ import annotations

import argparse
import csv
import json
import shutil
import sys
from datetime import date
from pathlib import Path

from bid_tracker import db as dbm
from bid_tracker import taxonomy
from bid_tracker.canonical import SPECS, load_package, write_csv
from bid_tracker.names import name_key, similarity

# --------------------------------------------------------------------------- formatting


def money(x) -> str:
    return "—" if x is None else f"${x:,.0f}"


def money2(x) -> str:
    return "—" if x is None else f"${x:,.2f}"


def pct(x) -> str:
    return "—" if x is None else f"{x:.1%}"


def ratio(x) -> str:
    return "—" if x is None else f"{x:.2f}"


def qfmt(q: dict, fmt=money) -> str:
    if q.get("p50") is not None:
        return f"p25 {fmt(q['p25'])} | p50 {fmt(q['p50'])} | p75 {fmt(q['p75'])}  (n={q['n']})"
    if q.get("values"):
        return "values " + ", ".join(fmt(v) for v in q["values"]) + f"  (n={q['n']}, too few for percentiles)"
    return f"no data (n={q.get('n', 0)})"


def table(headers: list[str], rows: list[list[str]]) -> str:
    widths = [max(len(str(h)), *(len(str(r[i])) for r in rows)) if rows else len(str(h)) for i, h in enumerate(headers)]
    line = "  ".join(str(h).ljust(w) for h, w in zip(headers, widths))
    out = [line, "  ".join("-" * w for w in widths)]
    out += ["  ".join(str(c).ljust(w) for c, w in zip(r, widths)) for r in rows]
    return "\n".join(out)


def emit(args, obj, text: str) -> None:
    print(json.dumps(obj, indent=2, default=str) if getattr(args, "json", False) else text)


# --------------------------------------------------------------------------- helpers


def open_db(args, init: bool = True):
    path = Path(args.db) if args.db else dbm.default_db_path()
    conn = dbm.connect(path)
    if init:
        dbm.init_db(conn)
    return conn, path


def guard_fixtures(args, path: Path) -> None:
    if getattr(args, "fixtures", False) and dbm.is_default_db(path):
        sys.exit("--fixtures needs a scratch DB (--db /tmp/x.db); refusing to load test data into the real DB")


def print_issues(issues) -> None:
    for i in issues:
        print(f"  {i}")


def private_dir() -> Path:
    return dbm.data_dir() / "private"


def merge_csv_row(path: Path, name: str, key: str, row: dict) -> None:
    cols = list(SPECS[name]) if name in SPECS else list(row)
    rows: list[dict] = []
    if path.exists():
        with open(path, newline="") as fh:
            rows = list(csv.DictReader(fh))
    for r in rows:
        if r.get(key) == row[key]:
            r.update({k: v for k, v in row.items() if v not in (None, "")})
            break
    else:
        rows.append(row)
    write_csv(path, cols, rows)


# --------------------------------------------------------------------------- commands


def cmd_init(args):
    conn, path = open_db(args, init=False)
    dbm.init_db(conn, seed=not args.no_seed)
    print(f"initialised {path}")
    print(json.dumps(dbm.table_counts(conn)))


def cmd_status(args):
    conn, path = open_db(args)
    counts = dbm.table_counts(conn)
    last = conn.execute("SELECT * FROM ingest_runs ORDER BY run_id DESC LIMIT 5").fetchall()
    obj = {"db": str(path), "data_dir": str(dbm.data_dir()), "counts": counts, "recent_runs": [dict(r) for r in last]}
    text = [f"DB: {path}", f"data dir: {dbm.data_dir()}", json.dumps(counts)]
    text += [f"  run {r['run_id']} {r['started_at']} {r['status']}: {r['summary']}" for r in last]
    emit(args, obj, "\n".join(text))


def cmd_validate(args):
    from bid_tracker.importer import known_context
    from bid_tracker.validate import has_errors, issues_json, validate_package

    conn, path = open_db(args)
    guard_fixtures(args, path)
    issues = validate_package(load_package(args.package), fixtures=args.fixtures, **known_context(conn))
    if args.json:
        print(issues_json(issues))
    else:
        print_issues(issues)
        errors = sum(i.severity == "ERROR" for i in issues)
        print(f"{errors} errors, {len(issues) - errors} warnings")
    if has_errors(issues) or (args.strict and issues):
        sys.exit(1)


def cmd_import(args):
    from bid_tracker.importer import import_package

    conn, path = open_db(args)
    guard_fixtures(args, path)
    res = import_package(conn, args.package, feed=args.feed, fixtures=args.fixtures, dry_run=args.dry_run)
    print_issues(res.issues)
    if res.status == "failed":
        sys.exit(f"import refused: {sum(i.severity == 'ERROR' for i in res.issues)} validation errors")
    print(("dry run OK: " if args.dry_run else f"run {res.run_id}: ") + res.summary())


def apply_alias_file(conn) -> int:
    """Re-apply manual bidder merges (private/bidder_aliases.csv) before replaying packages."""
    p = private_dir() / "bidder_aliases.csv"
    if not p.exists():
        return 0
    n = 0
    with open(p, newline="") as fh:
        for r in csv.DictReader(fh):
            key = name_key(r["canonical_name"])
            row = conn.execute("SELECT bidder_id FROM bidders WHERE name_key = ?", (key,)).fetchone()
            bid = row[0] if row else conn.execute(
                "INSERT INTO bidders(canonical_name, name_key, fl_license_no) VALUES (?,?,?)",
                (r["canonical_name"], key, r.get("fl_license_no") or None)).lastrowid
            conn.execute("INSERT OR REPLACE INTO bidder_aliases(alias_key, bidder_id, alias_raw) VALUES (?,?,?)",
                         (name_key(r["alias_raw"]), bid, r["alias_raw"]))
            n += 1
    conn.commit()
    return n


def cmd_rebuild(args):
    from bid_tracker.areas import coverage
    from bid_tracker.importer import import_package, preload_agencies
    from bid_tracker.notion import MAP_FILE, load_map, save_map

    data = dbm.data_dir()
    if not (data / "packages").is_dir():
        sys.exit(f"no packages/ under {data}: is BID_TRACKER_DATA set to the data repo clone?")
    path = Path(args.db) if args.db else dbm.default_db_path()
    map_path = path.parent / MAP_FILE
    if path.exists():
        if not map_path.exists():   # DB from before the map file existed: keep its Notion page ids
            old = dbm.connect(path)
            dbm.init_db(old)
            save_map(old, map_path)
            old.close()
        backup = path.with_suffix(".db.bak")
        shutil.move(path, backup)
        print(f"moved old DB to {backup}")
    conn = dbm.connect(path)
    dbm.init_db(conn)
    print(f"aliases applied: {apply_alias_file(conn)}")
    print(f"Notion page ids restored: {load_map(conn, map_path)}")
    dirs = sorted(p for p in (data / "index").glob("*") if p.is_dir())
    dirs += sorted(p for p in (data / "packages").glob("*") if p.is_dir())
    if (data / "private").is_dir():
        dirs.append(data / "private")
    print(f"agencies preloaded: {preload_agencies(conn, dirs)}")
    failed = 0
    for d in dirs:
        res = import_package(conn, d, feed="manual")
        status = "OK " if res.status == "ok" else "ERR"
        print(f"{status} {d.relative_to(data)}: {res.summary() if res.status == 'ok' else ''}")
        if res.status != "ok":
            failed += 1
            print_issues([i for i in res.issues if i.severity == "ERROR"])
    print(json.dumps(dbm.table_counts(conn)))
    orphans = coverage(conn)["orphans"]
    if orphans:
        print(f"area rows with no solicitation: {len(orphans)} (see `areas --orphans`)")
    if failed:
        sys.exit(f"{failed} package(s) failed validation")


def cmd_ingest(args):
    from bid_tracker.importer import import_package

    conn, _ = open_db(args)
    today = date.today().isoformat()
    if args.adapter == "bls-ppi":
        from bid_tracker.adapters import bls_ppi

        out = Path(args.out) if args.out else dbm.data_dir() / "index" / f"{today}-bls-ppi"
        out, n = bls_ppi.build_package(out, start_year=args.start_year)
    else:
        from bid_tracker.adapters import socrata

        if not args.source:
            sys.exit("ingest socrata needs --source NAME (a [[socrata]] block in sources.toml)")
        out = Path(args.out) if args.out else dbm.data_dir() / "packages" / f"{today}-socrata-{args.source}"
        out, n = socrata.build_package(args.source, out, since=args.since)
    print(f"wrote {n} rows to {out}")
    if not args.no_import:
        res = import_package(conn, out, feed="manual")
        print_issues(res.issues)
        print(res.summary() if res.status == "ok" else "import refused")


def cmd_escalate(args):
    from bid_tracker.escalation import escalate

    conn, _ = open_db(args)
    value, esc = escalate(conn, args.amount, f"{args.from_period}-01", to_period=args.to,
                          series_id=args.series, project_type=args.project_type)
    obj = {"amount": args.amount, "escalated": value, "factor": esc.factor, "series": esc.series_id,
           "from": esc.from_period, "to": esc.to_period, "flags": esc.flags}
    emit(args, obj, f"{money(args.amount)} ({esc.from_period}) -> {money(value)} ({esc.to_period}) "
                    f"x{ratio(esc.factor)} via {esc.series_id}" + (f"  [{'; '.join(esc.flags)}]" if esc.flags else ""))


def cmd_pdf_text(args):
    from bid_tracker.pdftext import extract_text, parse_pages

    print(extract_text(args.pdf, parse_pages(args.pages)))


def cmd_stats(args):
    from bid_tracker.stats import agency_stats, solicitation_stats

    conn, _ = open_db(args)
    if args.agency:
        obj = agency_stats(conn, args.agency, args.since)
        text = (f"{args.agency}: {obj['tabs']} low-bid tabs\n  bidders {qfmt(obj['bidders'], ratio)}\n"
                f"  gap     {qfmt(obj['gap'], pct)}\n  low/EE  {qfmt(obj['low_ee'], ratio)}\n  CV      {qfmt(obj['cv'], pct)}")
        return emit(args, obj, text)
    obj = solicitation_stats(conn, args.sol_ref)
    if obj is None:
        sys.exit(f"{args.sol_ref} not found")
    s, st = obj["solicitation"], obj["stats"]
    lines = [f"{s['sol_ref']}  {s['title']}", f"  {s['agency_name']} · {s['project_type']} · opened {s['bid_open_date']}"
             f" · SF {s['gsf'] or '—'} ({s['area_kind'] or 'no area'}) · EE {money(s['engineers_estimate'])} ({s['ee_source'] or '—'})",
             f"  bidders {st['n']} · low {money(st['low'])} · second {money(st['second'])} · gap {pct(st['gap'])}"
             f" · low/median {ratio(st['low_median'])} · low/EE {ratio(st['low_ee'])} · CV {pct(st['cv'])}"
             f" · low $/SF {money2(st['low_psf'])}", ""]
    scored = any(b["score_total"] is not None for b in obj["bids"])
    lines.append(table(["#", "Bidder", "Total"] + (["Score"] if scored else []) + ["Awardee", "Ideal"],
                       [[b["price_rank"] or ("NR" if b["responsive"] == 0 else ""), b["canonical_name"],
                         money(b["total_bid"])] + ([ratio(b["score_total"])] if scored else [])
                        + ["yes" if b["is_awardee"] else "", "yes" if b["is_ideal"] else ""] for b in obj["bids"]]))
    emit(args, obj, "\n".join(lines))


def cmd_benchmark(args):
    from bid_tracker.benchmark import benchmark

    conn, _ = open_db(args)
    obj = benchmark(conn, project_type=args.project_type, agency_type=args.agency_type, region=args.region,
                    size=args.size_band, gsf=args.gsf, est_amount=args.amount, since=args.since,
                    area_kind=args.area_kind)
    lines = [f"segment {obj['key']}  since {obj['since']}  n={obj['n']}  escalated to {obj['escalated_to']}"]
    lines += [f"  ! {w}" for w in obj["warnings"] + obj["escalation_flags"]]
    lines += [f"  low $/SF (esc) {qfmt(obj['low_psf_esc'], money2)}  [{obj['low_psf_kind'] or 'no area'}]", f"  low bid (esc)  {qfmt(obj['low_esc'])}",
              f"  low / EE       {qfmt(obj['low_ee'], ratio)}", f"  bidders        {qfmt(obj['bidders'], ratio)}",
              f"  gap low->2nd   {qfmt(obj['gap'], pct)}", f"  spread (CV)    {qfmt(obj['cv'], pct)}", ""]
    if obj["sample"]:
        lines.append(table(["Ref", "Opened", "N", "Low", "Low (esc)", "SF", "Area", "Low/EE"],
                           [[t["sol_ref"], t["bid_open_date"], t["n"], money(t["low"]), money(t["low_esc"]),
                             t["gsf"] or "—", t["area_kind"] or "—", ratio(t["low_ee"])] for t in obj["sample"]]))
    emit(args, obj, "\n".join(lines))


def cmd_areas(args):
    from bid_tracker.areas import coverage

    conn, _ = open_db(args)
    obj = coverage(conn, dbm.data_dir() / "area_misses.csv")
    lines = []
    if not args.orphans:
        c = obj["coverage"]
        lines.append(f"vertical per-project tabs with an area: {c['with_area']}/{c['tabs']} ({pct(c['share'])})")
        lines += [f"  {k}: {v['with_area']}/{v['tabs']}" for k, v in obj["by_type"].items()]
        if obj["missing"]:
            lines += ["", table(["Ref", "Type", "Opened", "Tried", "Last tried"],
                                [[m["sol_ref"], m["project_type"], m["bid_open_date"], (m["searched"] or "—")[:60],
                                  m["last_tried"] or "—"] for m in obj["missing"]])]
    if obj["orphans"]:
        lines += ["", "area rows with no solicitation (re-keyed or mistyped sol_ref):"]
        lines += [f"  {o['sol_ref']} {o['area_kind']} {o['sf']:,.0f}" for o in obj["orphans"]]
    emit(args, obj, "\n".join(lines))


def cmd_rates(args):
    from bid_tracker.rates import cliffs, rate_bands

    conn, _ = open_db(args)
    bands = rate_bands(conn, args.service, args.since)
    cl = cliffs(conn, args.sol_ref)
    lines = [table(["Service", "Bucket", "Competitors $/SF", "Awardees $/SF", "Ideal $/SF", "Ideal %ile"],
                   [[b["service"], b["bucket"] + (" *" if b["derived"] else ""), qfmt(b["all_bidders"], money2),
                     qfmt(b["awardees"], money2), money2(b["ideal_psf"]), pct(b["ideal_percentile"])] for b in bands]),
             "* lump-sum bucket converted at its midpoint size (derived)"]
    if cl:
        lines += ["", "Price cliffs at bucket boundaries:"]
        lines += [f"  {c['sol_ref']} {c['bidder']} {c['service']}: {c['from_bucket']} -> {c['to_bucket']} "
                  f"{money(c['price_at_top'])} -> {money(c['price_at_next'])} ({c['jump']:.2f}x)" for c in cl]
    emit(args, {"bands": bands, "cliffs": cl}, "\n".join(lines))


def cmd_competitors(args):
    from bid_tracker.competitors import head_to_head, profiles

    conn, _ = open_db(args)
    if args.vs_ideal:
        h = head_to_head(conn)
        return emit(args, h, table(["Competitor", "Shared tabs", "Ideal lower", "Ideal/them"],
                                   [[x["name"], x["shared_tabs"], x["ideal_lower"], ratio(x["ideal_over_them"])] for x in h]))
    p = profiles(conn, name=args.name, top=args.top, since=args.since)
    emit(args, p, table(["Bidder", "Bids", "Wins", "Lows", "Win rate", "Med above low", "Med bid/EE", "Rank %ile", "Last bid"],
                        [[x["name"][:40], x["bids"], x["wins"], x["low_bids"], pct(x["win_rate"]), pct(x["pct_above_low"]),
                          ratio(x["bid_ee"]), ratio(x["rank_pctile"]), x["last_bid"]] for x in p]))


def cmd_position(args):
    from bid_tracker.position import best_value, markup_grid, position

    conn, _ = open_db(args)
    grid = markup_grid(args.markups)
    if args.method == "best_value":
        if not (args.competitor_price and args.price_weight):
            sys.exit("best-value mode needs --competitor-price and --price-weight")
        obj = best_value(cost=args.cost, competitor_price=args.competitor_price, weight=args.price_weight,
                         nonprice_gap=args.nonprice_gap, formula=args.price_formula, markups=grid)
        lines = [f"best value: cost {money(args.cost)}, competitor {money(args.competitor_price)}, price weight "
                 f"{args.price_weight}, their non-price lead {args.nonprice_gap}",
                 f"  break-even bid {money(obj['breakeven_bid'])}"]
        lines += [f"  ! {f}" for f in obj["flags"]]
        lines.append(table(["Markup", "Bid", "Our pts", "Their pts", "Net"],
                           [[pct(r["markup"]), money(r["bid"]), f"{r['our_points']:.2f}", f"{r['their_points']:.2f}",
                             f"{r['net']:+.2f}"] for r in obj["table"]]))
        return emit(args, obj, "\n".join(lines))
    try:
        obj = position(conn, cost=args.cost, ee=args.ee, expected_median=args.expected_median,
                       project_type=args.project_type, agency_type=args.agency_type, region=args.region, gsf=args.gsf,
                       bidders=args.bidders, markups=grid, bid_cost=args.bid_cost, mode=args.mode, since=args.since)
    except ValueError as exc:
        sys.exit(str(exc))
    lines = [f"mode {obj['mode']} · cost {money(obj['cost'])} · reference {money(obj['reference'])} · "
             f"segment {obj['segment']} · {obj['n_ratios']} competitor bids on {obj['n_tabs']} tabs"]
    if "refused" in obj:
        lines.append(f"  REFUSED: {obj['refused']}")
    else:
        lines += [f"  ! {f}" for f in obj["flags"]]
        lines.append(f"  fit: ln(bid/ref) ~ N({obj['mu']:.3f}, {obj['sigma']:.3f}); competitors "
                     + ", ".join(f"{k}: {p:.0%}" for k, p in sorted(obj["k_dist"].items())))
        lines.append(table(["Markup", "Bid", "P(beat one) fit", "empirical", "P(win)", "E[profit]"],
                           [[pct(r["markup"]) + (" <" if r["markup"] == obj["m_star"] else ""), money(r["bid"]),
                             pct(r["p1_fit"]), pct(r["p1_empirical"]), pct(r["p_win"]), money(r["expected_profit"])]
                            for r in obj["table"]]))
        lines.append(f"  max expected profit at {pct(obj['m_star'])} markup ({money(obj['best']['bid'])})")
    lines += ["", "Caveats:"] + [f"  - {c}" for c in obj["caveats"]]
    if args.save and "refused" not in obj:
        from bid_tracker.importer import upsert_pursuit

        snap = {k: obj[k] for k in ("mode", "cost", "reference", "segment", "n_ratios", "n_tabs", "mu", "sigma", "m_star")}
        row = {"sol_ref": args.save, "est_cost_pre_ohp": args.cost}
        merge_csv_row(private_dir() / "ideal_pursuits.csv", "ideal_pursuits.csv", "sol_ref",
                      {"sol_ref": args.save, "est_cost_pre_ohp": f"{args.cost:.2f}"})
        if upsert_pursuit(conn, row):
            conn.execute("UPDATE ideal_pursuits SET position_json = ? WHERE solicitation_id = "
                         "(SELECT solicitation_id FROM solicitations WHERE sol_ref = ?)", (json.dumps(snap), args.save))
            conn.commit()
            lines.append(f"saved position snapshot on pursuit {args.save}")
        else:
            lines.append(f"! {args.save} not in DB; add the solicitation first to save the snapshot")
    emit(args, obj, "\n".join(lines))


def cmd_gonogo(args):
    from bid_tracker.gonogo import gonogo

    conn, _ = open_db(args)
    try:
        obj = gonogo(conn, sol_ref=args.sol_ref, cost=args.cost, project_type=args.project_type,
                     agency_id=args.agency, gsf=args.gsf)
    except ValueError as exc:
        sys.exit(str(exc))
    lines = [f"{obj['verdict']}  {obj['sol_ref'] or ''} {obj['project_type']} @ {obj['agency_id']} "
             f"(est. bid {money(obj['estimated_bid'])})"]
    lines += [f"  [{f['level']}] {f['message']}" for f in obj["flags"]] or ["  no flags"]
    bm = obj["benchmark"]
    lines.append(f"  comparable tabs: n={bm['n']} {bm['key']}; low (esc) {qfmt(bm['low_esc'])}")
    emit(args, obj, "\n".join(lines))


def cmd_pursuit(args):
    from bid_tracker.importer import upsert_pursuit

    conn, _ = open_db(args)
    row = {"sol_ref": args.sol_ref, "decision": args.decision, "decision_date": args.decision_date,
           "decision_reason": args.reason, "est_direct_cost": args.est_direct_cost,
           "est_cost_pre_ohp": args.est_cost, "bid_amount": args.bid, "markup_pct": args.markup,
           "result": args.result, "rank": args.rank, "score_total": args.score, "debrief": args.debrief,
           "lessons": args.lessons, "estimate_dir": args.estimate_dir}
    if args.decision and not args.decision_date:
        row["decision_date"] = date.today().isoformat()
    if not upsert_pursuit(conn, row):
        sys.exit(f"{args.sol_ref} is not in the DB; import the solicitation (even as award_status=open) first")
    conn.commit()
    merge_csv_row(private_dir() / "ideal_pursuits.csv", "ideal_pursuits.csv", "sol_ref",
                  {k: ("" if v is None else v) for k, v in row.items()})
    print(f"pursuit {args.sol_ref} saved (DB + {private_dir() / 'ideal_pursuits.csv'})")


def cmd_bidders(args):
    conn, _ = open_db(args)
    if args.action == "review":
        rows = conn.execute("SELECT bidder_id, canonical_name, name_key FROM bidders").fetchall()
        pairs = []
        for i, a in enumerate(rows):
            for b in rows[i + 1:]:
                s = similarity(a["canonical_name"], b["canonical_name"])
                if s >= args.threshold:
                    pairs.append([a["canonical_name"], b["canonical_name"], f"{s:.2f}"])
        print(table(["Bidder A", "Bidder B", "Similarity"], pairs) if pairs else "no likely duplicates")
        return
    keep, drop = (conn.execute("SELECT * FROM bidders WHERE name_key = ?", (name_key(n),)).fetchone() for n in (args.keep, args.drop))
    if not keep or not drop:
        sys.exit("both names must match an existing bidder (see `bidders review`)")
    aliases = [r[0] for r in conn.execute("SELECT alias_raw FROM bidder_aliases WHERE bidder_id = ?", (drop["bidder_id"],))]
    for alias in {drop["canonical_name"], *aliases}:
        merge_csv_row(private_dir() / "bidder_aliases.csv", "bidder_aliases", "alias_raw",
                      {"canonical_name": keep["canonical_name"], "alias_raw": alias, "fl_license_no": keep["fl_license_no"] or ""})
    for t, col in (("bids", "bidder_id"), ("rate_cards", "bidder_id"), ("solicitations", "awardee_bidder_id"),
                   ("bidder_aliases", "bidder_id")):
        conn.execute(f"UPDATE OR IGNORE {t} SET {col} = ? WHERE {col} = ?", (keep["bidder_id"], drop["bidder_id"]))
    conn.execute("DELETE FROM bidders WHERE bidder_id = ?", (drop["bidder_id"],))
    conn.commit()
    print(f"merged {drop['canonical_name']!r} into {keep['canonical_name']!r} (recorded in private/bidder_aliases.csv)")


def cmd_export_xlsx(args):
    from bid_tracker.export_xlsx import build

    conn, _ = open_db(args)
    out = Path(args.out) if args.out else dbm.data_dir() / "exports" / f"FL-Bid-Pricing-{date.today().isoformat()}.xlsx"
    print(f"wrote {build(conn, out, since=args.since)}")


def cmd_notion_schema(args):
    from bid_tracker.notion import NOTION_SCHEMA, ddl

    for key, spec in NOTION_SCHEMA.items():
        print(f"-- {spec['title']} ({key}): {spec['description']}")
        print(ddl(key))
        for name, target in spec["relations"].items():
            print(f"-- relation: \"{name}\" -> {NOTION_SCHEMA[target]['title']}")
        print()


def cmd_export_notion(args):
    from bid_tracker.notion import export

    conn, _ = open_db(args)
    mapped = conn.execute("SELECT COUNT(*) FROM notion_map").fetchone()[0]
    rows = conn.execute("SELECT COUNT(*) FROM solicitations").fetchone()[0]
    if rows and not mapped and not args.first_sync:
        sys.exit("notion_map is empty but the DB has rows, so every Notion page would be created again. "
                 "Check BID_TRACKER_DATA (`status`) and that notion_map.csv was restored by `rebuild`. "
                 "Pass --first-sync only for a brand-new, empty Notion workspace.")
    out_root = Path(args.out) if args.out else dbm.data_dir() / "notion_out"
    path = export(conn, out_root, all_rows=args.all, feed=args.feed)
    m = json.loads(path.read_text())
    by: dict[str, dict[str, int]] = {}
    for op in m["ops"]:
        by.setdefault(op["db"], {}).setdefault(op["op"], 0)
        by[op["db"]][op["op"]] += 1
    pending = sum(1 for op in m["ops"] if op.get("pending_relations"))
    print(f"wrote {path}\n  ops: {json.dumps(by)}  pending relations: {pending}")


def cmd_notion_orphans(args):
    from bid_tracker.notion import MAP_FILE, forget, orphan_bidders, save_map

    conn, path = open_db(args)
    rows = orphan_bidders(conn)
    print(json.dumps(rows, indent=1))
    if args.forget and rows:
        n = forget(conn, "bidder", [r["local_ref"] for r in rows])
        print(f"forgot {n} bidder page ids; wrote {save_map(conn, path.parent / MAP_FILE)} to {path.parent / MAP_FILE}")


def cmd_notion_ack(args):
    from bid_tracker.notion import MAP_FILE, ack, save_map

    conn, path = open_db(args)
    acks = json.loads(Path(args.acks).read_text())
    print(f"recorded {ack(conn, acks)} Notion page ids")
    map_path = path.parent / MAP_FILE
    print(f"wrote {save_map(conn, map_path)} page ids to {map_path} (commit it with the data)")


# --------------------------------------------------------------------------- parser


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="python3 -m bid_tracker", description="FL public bid pricing tracker")
    p.add_argument("--db", help="SQLite path (default $BID_TRACKER_DB or $BID_TRACKER_DATA/bids.db)")
    sub = p.add_subparsers(dest="command", required=True)

    def add(name, fn, help_):
        sp = sub.add_parser(name, help=help_)
        sp.set_defaults(fn=fn)
        sp.add_argument("--json", action="store_true", help="machine-readable output")
        return sp

    sp = add("init", cmd_init, "create the DB and load reference data")
    sp.add_argument("--no-seed", action="store_true")
    add("status", cmd_status, "row counts and recent runs")
    sp = add("rebuild", cmd_rebuild, "rebuild the DB by replaying every package in $BID_TRACKER_DATA")
    for name, fn, help_ in (("validate", cmd_validate, "check an import package"),
                            ("import-csv", cmd_import, "validate and load an import package")):
        sp = add(name, fn, help_)
        sp.add_argument("package")
        sp.add_argument("--fixtures", action="store_true", help="synthetic test data (scratch DB only)")
        if name == "validate":
            sp.add_argument("--strict", action="store_true", help="fail on warnings too")
        else:
            sp.add_argument("--feed", default="manual", choices=["weekday", "weekly", "manual"])
            sp.add_argument("--dry-run", action="store_true")
    sp = add("ingest", cmd_ingest, "pull a machine-readable source into a package (and import it)")
    sp.add_argument("adapter", choices=["bls-ppi", "socrata"])
    sp.add_argument("--source")
    sp.add_argument("--since")
    sp.add_argument("--start-year", type=int)
    sp.add_argument("--out")
    sp.add_argument("--no-import", action="store_true")
    sp = add("refresh-index", lambda a: cmd_ingest(argparse.Namespace(**{**vars(a), "adapter": "bls-ppi"})),
             "refresh BLS PPI escalation series")
    sp.add_argument("--start-year", type=int)
    sp.add_argument("--out")
    sp.add_argument("--no-import", action="store_true")
    sp.set_defaults(source=None, since=None)
    sp = add("escalate", cmd_escalate, "escalate an amount between periods")
    sp.add_argument("--amount", type=float, required=True)
    sp.add_argument("--from", dest="from_period", required=True, help="YYYY-MM")
    sp.add_argument("--to", help="YYYY-MM (default: latest index value)")
    sp.add_argument("--series")
    sp.add_argument("--project-type")
    sp = add("pdf-text", cmd_pdf_text, "extract text from a bid-tab PDF")
    sp.add_argument("pdf")
    sp.add_argument("--pages", help="e.g. 1-3,5")
    sp = add("stats", cmd_stats, "statistics for one tab or one agency")
    sp.add_argument("sol_ref", nargs="?")
    sp.add_argument("--agency")
    sp.add_argument("--since")
    sp = add("benchmark", cmd_benchmark, "segment benchmark: what comparable jobs went for")
    sp.add_argument("--project-type")
    sp.add_argument("--agency-type")
    sp.add_argument("--region")
    sp.add_argument("--size-band")
    sp.add_argument("--gsf", type=float, help="area of the kind the project type uses (see `areas`)")
    sp.add_argument("--area-kind", choices=taxonomy.AREA_KINDS, help="compare $/SF on this kind of area")
    sp.add_argument("--amount", type=float, help="expected bid, for a dollar size band when GSF is unknown")
    sp.add_argument("--since", default="2023-01-01")
    sp = add("areas", cmd_areas, "square-footage coverage: vertical tabs with no area, and orphan area rows")
    sp.add_argument("--orphans", action="store_true", help="only area rows whose sol_ref isn't in the DB")
    sp = add("rates", cmd_rates, "term/disaster rate-card bands and price cliffs")
    sp.add_argument("--service")
    sp.add_argument("--since")
    sp.add_argument("--sol-ref")
    sp = add("competitors", cmd_competitors, "competitor profiles")
    sp.add_argument("--name")
    sp.add_argument("--top", type=int, default=25)
    sp.add_argument("--since")
    sp.add_argument("--vs-ideal", action="store_true")
    sp = add("position", cmd_position, "P(win) and expected profit by markup")
    sp.add_argument("--cost", type=float, required=True, help="cost before OH&P (direct + GCs + bonds + insurance)")
    sp.add_argument("--ee", type=float, help="this job's engineer's estimate")
    sp.add_argument("--expected-median", type=float)
    sp.add_argument("--project-type")
    sp.add_argument("--agency-type")
    sp.add_argument("--region")
    sp.add_argument("--gsf", type=float)
    sp.add_argument("--bidders", type=int, help="expected number of bidders including Ideal")
    sp.add_argument("--markups", default="0:0.20:0.01")
    sp.add_argument("--bid-cost", type=float, default=0.0)
    sp.add_argument("--mode", choices=["ee", "median", "own"])
    sp.add_argument("--since", default="2023-01-01")
    sp.add_argument("--method", choices=["low_bid", "best_value"], default="low_bid")
    sp.add_argument("--competitor-price", type=float)
    sp.add_argument("--price-weight", type=float)
    sp.add_argument("--price-formula", choices=["ratio", "linear"], default="ratio")
    sp.add_argument("--nonprice-gap", type=float, default=0.0)
    sp.add_argument("--save", metavar="SOL_REF", help="store the snapshot on Ideal's pursuit")
    sp = add("gonogo", cmd_gonogo, "go/no-go flags")
    sp.add_argument("sol_ref", nargs="?")
    sp.add_argument("--cost", type=float)
    sp.add_argument("--project-type")
    sp.add_argument("--agency")
    sp.add_argument("--gsf", type=float)
    sp = add("pursuit", cmd_pursuit, "record Ideal's own decision, bid and result")
    sp.add_argument("action", choices=["add", "update"])
    sp.add_argument("sol_ref")
    sp.add_argument("--decision", choices=["go", "no_go", "pending"])
    sp.add_argument("--decision-date")
    sp.add_argument("--reason")
    sp.add_argument("--est-direct-cost", type=float)
    sp.add_argument("--est-cost", type=float, help="cost before OH&P")
    sp.add_argument("--bid", type=float)
    sp.add_argument("--markup", type=float, help="fraction, 0.08 = 8%%")
    sp.add_argument("--result", choices=["won", "lost", "no_bid", "rejected", "pending", "cancelled"])
    sp.add_argument("--rank", type=int)
    sp.add_argument("--score", type=float)
    sp.add_argument("--debrief")
    sp.add_argument("--lessons")
    sp.add_argument("--estimate-dir")
    sp = add("bidders", cmd_bidders, "review likely duplicate bidders, or merge two")
    sp.add_argument("action", choices=["review", "merge"])
    sp.add_argument("keep", nargs="?")
    sp.add_argument("drop", nargs="?")
    sp.add_argument("--threshold", type=float, default=0.88)
    sp = add("export-xlsx", cmd_export_xlsx, "Excel workbook of the tracker")
    sp.add_argument("--out")
    sp.add_argument("--since")
    add("notion-schema", cmd_notion_schema, "print the Notion database DDL")
    sp = add("export-notion", cmd_export_notion, "write the Notion sync manifest")
    sp.add_argument("--all", action="store_true", help="include unchanged rows")
    sp.add_argument("--feed", default="manual", choices=["weekday", "weekly", "manual"])
    sp.add_argument("--out")
    sp.add_argument("--first-sync", action="store_true", help="allow an empty notion_map (brand-new workspace only)")
    sp = add("notion-orphans", cmd_notion_orphans, "list bidder pages of merged-away firms; --forget drops them from the map")
    sp.add_argument("--forget", action="store_true")
    sp = add("notion-ack", cmd_notion_ack, "record Notion page ids after applying a manifest")
    sp.add_argument("acks")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "bidders" and args.action == "merge" and not (args.keep and args.drop):
        sys.exit("bidders merge KEEP DROP")
    if args.command == "stats" and not (args.sol_ref or args.agency):
        sys.exit("stats needs a SOL_REF or --agency")
    args.fn(args)
    return 0
