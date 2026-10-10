#!/usr/bin/env python3
"""Deterministic takeoff validator — machine checks for the takeoff accuracy protocol.

Usage:
    python3 estimating/scripts/validate_takeoff.py <project_dir>
            [--sector residential|commercial|ti|public] [--golden golden.csv] [--strict]

Reads <project_dir>/takeoff.md (structure: estimating/templates/takeoff-template.md)
and, if present, <project_dir>/lineitems.csv. Checks:
  required sections; sheet index coverage; scale log (recomputes each check-dim
  delta and grades it confirmed <=1% / amber <=5% / red >5%); every quantity line has
  a unique ID, CSI division, numeric qty (or RFI), unit, gross/net on areas, a source
  sheet, and method/confidence from the allowed sets (scaled => approx); Withheld IDs
  kept out of the totals and the CSV; takeoff <-> seed-CSV tie-out by line_id; QA block
  completeness; the protocol §13 ratio screen; and, with --golden, a regression
  compare against verified quantities.

golden.csv columns: id,item,qty,unit,tol_pct  (match by id, else by exact item name).

Exit code 0 = no FAILs (WARNs allowed; --strict fails WARNs too), 1 = FAIL.
"""

import argparse
import csv
import re
import sys
from collections import defaultdict
from pathlib import Path

CORE_HEADER = ["division", "section", "item", "description", "qty", "unit",
               "unit_mat", "unit_lab", "unit_equip", "unit_sub", "waste_pct", "notes"]
PROVENANCE = ["line_id", "source_sheet", "method", "confidence", "price_basis"]

CSI_DIVS = {f"{i:02d}" for i in range(1, 50)}
METHODS = {"measured", "counted", "calculated", "imported", "scaled"}
CONFIDENCE = {"med-high", "med", "approx", "assumed", "rfi"}
CONF_ALIASES = {"med-high/measured": "med-high", "medium-high": "med-high", "medium": "med"}
SCALE_SOURCES = {"title-block", "viewport-note", "scale-bar", "calibrated", "nts"}
SCALE_STATUS = {"confirmed", "amber", "red", "nts", "unconfirmed"}
READ_STATES = {"read", "partial", "not read", "n/a"}
AREA_UNITS = {"SF", "SY"}
UNIT_WHITELIST = {
    "EA", "LF", "SF", "SY", "CY", "SQ", "TON", "TONS", "LBS", "LB", "LS",
    "ALLOW", "MBF", "BF", "GAL", "HR", "DAY", "WK", "MO", "SET", "PR", "CF",
    "RL", "BX", "CT", "KIT",
}
QA_MIN_BOXES = 17          # boxes in protocol §14
SHEET_RE = re.compile(r"\b(?!RFI)[A-Z]{1,3}-?\d{1,3}(?:\.\d{1,2})?[A-Z]?\b")
PLACEHOLDER_RE = re.compile(r"\{\{.*?\}\}")
QA_CHECKED = ("☑", "✅", "✔", "[x]", "[X]")
QA_UNCHECKED = ("□", "☐", "[ ]")
# An unmet box must say why, explicitly: "□ Ratio checks run — FAILED: no GFA, RFI-07"
QA_REASON_RE = re.compile(r"\b(FAILED|NOT MET|N/A)\s*[:—–-]\s*\S", re.I)

# Protocol §13 starred ratios: (lo, hi) screen bands per sector.
RATIO_BANDS = {
    "rebar_lb_per_cy": {"*": (40, 300)},
    "cmu_per_sf": {"*": (1.05, 1.20)},
    "sf_per_ton": {"residential": (350, 850), "commercial": (200, 500),
                   "ti": (200, 500), "public": (200, 500)},
    "gyp_sf_per_gfa": {"residential": (2.5, 4.5), "commercial": (1.5, 5.0),
                       "ti": (1.5, 5.0), "public": (1.5, 5.0)},
}


# ---------------------------------------------------------------- helpers

class Report:
    def __init__(self):
        self.rows = []

    def add(self, level, check, msg):
        self.rows.append((level, check, msg))

    def dump(self):
        order = {"FAIL": 0, "WARN": 1, "INFO": 2, "PASS": 3}
        counts = defaultdict(int)
        for level, check, msg in sorted(self.rows, key=lambda r: order[r[0]]):
            counts[level] += 1
            print(f"  [{level}] {check}: {msg}")
        print(f"\n  Summary: {counts['FAIL']} FAIL / {counts['WARN']} WARN / "
              f"{counts['INFO']} INFO / {counts['PASS']} PASS")
        return counts


def clip(items, n=8):
    return items if len(items) <= n else items[:n] + [f"…+{len(items) - n}"]


def num(s):
    """Parse a number ('1,234.5', '$12', '7%'); None if not numeric/blank."""
    s = str(s or "").strip().replace("$", "").replace(",", "").replace("%", "")
    try:
        return float(s) if s else None
    except ValueError:
        return None


LEN_FT_IN = re.compile(
    r"^\s*(\d+(?:\.\d+)?)\s*(?:'|′|ft)\s*(?:-?\s*(\d+(?:\.\d+)?)(?:\s+(\d+)/(\d+))?\s*(?:\"|″|in)?)?\s*$")
LEN_IN = re.compile(r"^\s*(\d+(?:\.\d+)?)\s*(?:\"|″|in)\s*$")


def parse_length_ft(s):
    """Feet-inches ("40'-0\"", "12'-6 1/2\"", "40 ft") or decimal feet -> feet."""
    s = str(s or "").strip().replace("’", "'").replace("”", '"')
    if not s:
        return None
    m = LEN_FT_IN.match(s)
    if m:
        ft = float(m.group(1))
        inch = float(m.group(2) or 0)
        if m.group(3):
            inch += float(m.group(3)) / float(m.group(4))
        return ft + inch / 12
    m = LEN_IN.match(s)
    if m:
        return float(m.group(1)) / 12
    return num(s)


def norm(s):
    return re.sub(r"\s+", " ", str(s or "").strip()).lower()


def sheet_key(s):
    return re.sub(r"[\s\-]", "", str(s or "")).upper()


def sections(md):
    """Map lower-cased H2 heading -> body text."""
    out, cur, buf = {}, None, []
    for line in md.splitlines():
        m = re.match(r"^##\s+(.*?)\s*$", line)
        if m:
            if cur is not None:
                out[cur] = "\n".join(buf)
            cur, buf = m.group(1).strip().lower(), []
        elif cur is not None:
            buf.append(line)
    if cur is not None:
        out[cur] = "\n".join(buf)
    return out


def find_section(secs, *prefixes):
    for name, body in secs.items():
        if any(name.startswith(p) for p in prefixes):
            return body
    return None


def parse_table(body):
    """First markdown table in body -> (header, rows as dicts). Skips separators,
    blank/ellipsis rows and template placeholder rows ({{...}})."""
    if body is None:
        return None, []
    lines = [l for l in body.splitlines() if l.strip().startswith("|")]
    if not lines:
        return None, []

    def cells(line):
        parts = line.strip().strip("|").split("|")
        return [c.strip() for c in parts]

    header = [norm(c) for c in cells(lines[0])]
    rows = []
    for line in lines[1:]:
        cs = cells(line)
        if all(re.fullmatch(r":?-{2,}:?", c) or not c for c in cs):
            continue
        if all(c in ("", "…", "...") for c in cs):
            continue
        if PLACEHOLDER_RE.search(line):
            continue
        cs += [""] * (len(header) - len(cs))
        rows.append(dict(zip(header, cs[:len(header)])))
    return header, rows


def col(row, *names):
    """Value of the first column whose header starts with any of names."""
    for key, val in row.items():
        if any(key.startswith(n) for n in names):
            return val
    return ""


# ---------------------------------------------------------------- checks

def check_sections(secs, md, rep):
    need = {"sheet index": ("sheet index",), "scale log": ("scale log",),
            "quantities": ("quantities",), "qa block": ("takeoff qa", "qa block", "qa")}
    want = {"withheld": ("withheld",), "rfis": ("rfi",)}
    missing_f = [k for k, p in need.items() if find_section(secs, *p) is None]
    missing_w = [k for k, p in want.items() if find_section(secs, *p) is None]
    if missing_f:
        rep.add("FAIL", "sections", f"missing required section(s): {missing_f} "
                "(use estimating/templates/takeoff-template.md headings)")
    if missing_w:
        rep.add("WARN", "sections", f"missing section(s): {missing_w} — add them, even if 'None'")
    if not missing_f and not missing_w:
        rep.add("PASS", "sections", "all template sections present")
    left = sorted(set(PLACEHOLDER_RE.findall(md)))
    if left:
        rep.add("WARN", "placeholders", f"template placeholders left in takeoff.md: {clip(left, 5)}")


def gross_floor_area(md):
    m = re.search(r"^\|\s*Gross floor area\s*\|\s*([^|]+)\|", md, re.I | re.M)
    if not m:
        return None
    return num(re.sub(r"[A-Za-z]", "", m.group(1)))


def check_sheet_index(secs, rep):
    _hdr, rows = parse_table(find_section(secs, "sheet index"))
    index = {}
    bad_state, unread = [], []
    for r in rows:
        sheet = col(r, "sheet")
        if not sheet:
            continue
        index[sheet_key(sheet)] = r
        state = norm(col(r, "read"))
        role = norm(col(r, "role"))
        notes = col(r, "notes")
        if state not in READ_STATES:
            bad_state.append(f"{sheet}: {state or 'blank'}")
        elif state in ("not read", "partial") and role in ("plan", "structural") and not notes:
            unread.append(f"{sheet} ({role}, {state})")
    if not index:
        rep.add("FAIL", "sheet-index", "sheet index table is empty")
        return index
    if bad_state:
        rep.add("WARN", "sheet-index", f"Read? not in {sorted(READ_STATES)}: {clip(bad_state)}")
    if unread:
        rep.add("FAIL", "sheet-coverage",
                f"plan/structural sheets not fully read with no reason: {clip(unread)}")
    else:
        rep.add("PASS", "sheet-coverage", f"{len(index)} sheets indexed; plan/structural coverage ok")
    return index


def check_scale_log(secs, rep):
    _hdr, rows = parse_table(find_section(secs, "scale log"))
    log, bad = {}, []
    graded = {"confirmed": 0, "amber": 0, "red": 0}
    for r in rows:
        sheet = col(r, "sheet")
        if not sheet:
            continue
        src, status = norm(col(r, "scale source")), norm(col(r, "status"))
        log[sheet_key(sheet)] = status
        if src not in SCALE_SOURCES:
            bad.append(("WARN", f"{sheet}: scale source {src or 'blank'!r} not in {sorted(SCALE_SOURCES)}"))
        if status not in SCALE_STATUS:
            bad.append(("FAIL", f"{sheet}: status {status or 'blank'!r} not in {sorted(SCALE_STATUS)}"))
            continue
        if status == "nts" or src == "nts":
            continue
        printed = parse_length_ft(col(r, "check dim (printed)", "check dim (print"))
        measured = parse_length_ft(col(r, "check dim (measured)", "check dim (meas"))
        if not printed or measured is None:
            bad.append(("FAIL", f"{sheet}: no parseable check dimension — scale unverified"))
            continue
        delta = abs(measured - printed) / printed * 100
        want = "confirmed" if delta <= 1 else ("amber" if delta <= 5 else "red")
        graded[want] += 1
        if status == "unconfirmed":
            bad.append(("FAIL", f"{sheet}: scale unconfirmed (Δ {delta:.2f}%)"))
        elif status != want:
            bad.append(("FAIL", f"{sheet}: logged {status!r} but check dim Δ = {delta:.2f}% → {want!r}"))
        elif want == "red":
            bad.append(("WARN", f"{sheet}: off-scale plot (Δ {delta:.2f}%) — confirm every "
                                f"measurement on it used the recalibrated scale"))
    for level, msg in bad:
        rep.add(level, "scale-gate", msg)
    if not rows:
        rep.add("WARN", "scale-gate", "scale log is empty — fine only if nothing was measured/scaled")
    elif not any(l == "FAIL" for l, _ in bad):
        rep.add("PASS", "scale-gate",
                f"{len(log)} sheet(s) logged — {graded['confirmed']} confirmed, "
                f"{graded['amber']} amber, {graded['red']} red (recalibrated)")
    return log


def check_quantities(secs, index, scale_log, rep):
    _hdr, rows = parse_table(find_section(secs, "quantities"))
    lines, problems = {}, defaultdict(list)
    for r in rows:
        lid = col(r, "id")
        item = col(r, "item")
        tag = f"{lid or '?'} {item[:36]}"
        if not lid:
            problems["missing-id"].append(tag)
            continue
        if lid in lines:
            problems["duplicate-id"].append(lid)
            continue
        div = col(r, "div").zfill(2) if col(r, "div").isdigit() else col(r, "div")
        unit = col(r, "unit").upper()
        method = norm(col(r, "method"))
        conf = norm(col(r, "confidence"))
        conf = CONF_ALIASES.get(conf, conf)
        gn = norm(col(r, "gross"))
        src = col(r, "source")
        qty = num(col(r, "qty"))
        lines[lid] = {"div": div, "item": item, "qty": qty, "unit": unit,
                      "method": method, "confidence": conf, "source": src}
        if div not in CSI_DIVS:
            problems["division"].append(f"{tag}: {div!r}")
        if qty is None and conf != "rfi":
            problems["qty"].append(tag)
        if unit and unit not in UNIT_WHITELIST:
            problems["unit"].append(f"{tag}: {unit}")
        if not unit:
            problems["unit-missing"].append(tag)
        if unit in AREA_UNITS and gn not in ("gross", "net"):
            problems["gross-net"].append(tag)
        if method not in METHODS:
            problems["method"].append(f"{tag}: {method or 'blank'}")
        if conf not in CONFIDENCE:
            problems["confidence"].append(f"{tag}: {conf or 'blank'}")
        if method == "scaled" and conf != "approx":
            problems["scaled-approx"].append(f"{tag}: {conf}")
        if not src:
            problems["source"].append(tag)
            continue
        sheets = [sheet_key(s) for s in SHEET_RE.findall(src)]
        if method != "imported" and index:
            unknown = [s for s in sheets if s not in index]
            if unknown:
                problems["source-index"].append(f"{tag}: {unknown}")
        if method in ("scaled", "measured"):
            ok = {"confirmed", "amber", "red"}
            if not any(scale_log.get(s) in ok for s in sheets):
                problems[f"scale-{method}"].append(f"{tag} ({src})")

    spec = [
        ("missing-id", "FAIL", "quantity rows with no ID"),
        ("duplicate-id", "FAIL", "duplicate IDs"),
        ("division", "FAIL", "blank/non-CSI division"),
        ("qty", "FAIL", "non-numeric qty on a non-RFI line"),
        ("unit-missing", "FAIL", "no unit"),
        ("unit", "WARN", "unit not in whitelist"),
        ("gross-net", "FAIL", "SF/SY line without gross/net declared (protocol §6)"),
        ("method", "FAIL", f"method not in {sorted(METHODS)}"),
        ("confidence", "FAIL", f"confidence not in {sorted(CONFIDENCE)}"),
        ("scaled-approx", "FAIL", "scaled lines must be confidence 'approx'"),
        ("source", "FAIL", "no source sheet"),
        ("source-index", "WARN", "source sheet not in the sheet index"),
        ("scale-scaled", "FAIL", "scaled off a sheet with no verified scale-log entry (§10)"),
        ("scale-measured", "WARN", "measured line's sheet has no scale-log entry — fine only if "
                                   "taken purely from printed dims; say so in Notes"),
    ]
    for key, level, msg in spec:
        if problems[key]:
            rep.add(level, f"qty-{key}", f"{msg}: {clip(problems[key])}")
    if not lines:
        rep.add("FAIL", "quantities", "quantities table is empty")
    elif not any(problems[k] for k, lvl, _ in spec if lvl == "FAIL"):
        by_conf = defaultdict(int)
        for ln in lines.values():
            by_conf[ln["confidence"]] += 1
        rep.add("PASS", "quantities", f"{len(lines)} lines; confidence mix {dict(by_conf)}")
    return lines


def check_withheld(secs, lines, rep):
    body = find_section(secs, "withheld")
    _hdr, rows = parse_table(body)
    ids = []
    for r in rows:
        wid = col(r, "id")
        if wid:
            ids.append(wid)
    clash = [w for w in ids if w in lines]
    if clash:
        rep.add("FAIL", "withheld", f"withheld IDs also in the quantities table (folded into totals): {clash}")
    elif body is not None:
        rep.add("PASS" if ids else "INFO", "withheld",
                f"{len(ids)} withheld item(s) kept out of totals" if ids else "no withheld items")
    return set(ids)


def check_qa(secs, rep):
    body = find_section(secs, "takeoff qa", "qa block", "qa") or ""
    checked = unchecked_ok = 0
    unchecked_bad = []
    for line in body.splitlines():
        s = line.strip()
        if s.startswith(QA_CHECKED):
            checked += 1
        elif s.startswith(QA_UNCHECKED):
            text = s.lstrip("□☐[] ").strip()
            if QA_REASON_RE.search(text):
                unchecked_ok += 1
            else:
                unchecked_bad.append(text[:60])
    total = checked + unchecked_ok + len(unchecked_bad)
    if total == 0:
        rep.add("FAIL", "qa-block", "no QA checkboxes found — paste protocol §14 and mark it")
        return
    if unchecked_bad:
        rep.add("FAIL", "qa-block", f"unchecked with no stated reason: {clip(unchecked_bad, 5)}")
    if unchecked_ok:
        rep.add("WARN", "qa-block", f"{unchecked_ok} box(es) unmet with a stated reason")
    if total < QA_MIN_BOXES:
        rep.add("WARN", "qa-block", f"{total} boxes found; protocol §14 has {QA_MIN_BOXES} — "
                                    "paste the current block")
    if not unchecked_bad and not unchecked_ok and total >= QA_MIN_BOXES:
        rep.add("PASS", "qa-block", f"all {total} boxes checked")


def check_csv(proj, lines, withheld, rep):
    path = proj / "lineitems.csv"
    if not path.exists():
        rep.add("INFO", "csv-tie-out", "lineitems.csv not present — tie-out skipped")
        return
    with path.open(newline="", encoding="utf-8-sig") as f:
        raw = list(csv.reader(f))
    if not raw:
        rep.add("FAIL", "csv-tie-out", "lineitems.csv is empty")
        return
    header = [h.strip() for h in raw[0]]
    if header == CORE_HEADER:
        rep.add("WARN", "csv-tie-out", "lineitems.csv has no provenance columns "
                f"({','.join(PROVENANCE)}) — takeoff ↔ CSV tie-out impossible")
        return
    if header != CORE_HEADER + PROVENANCE:
        rep.add("FAIL", "csv-tie-out", f"header is neither the 12-column core nor core + "
                f"{PROVENANCE}: {header}")
        return
    rows = [dict(zip(header, r)) for r in raw[1:] if any(c.strip() for c in r)]
    by_id = defaultdict(list)
    untraced, orphans, leaked = [], [], []
    for i, r in enumerate(rows, start=2):
        lid = r.get("line_id", "").strip()
        if not lid:
            if r.get("division", "").strip() != "01":
                untraced.append(f"row {i} [{r.get('division')}] {r.get('item', '')[:30]}")
            continue
        if lid in withheld:
            leaked.append(f"row {i}: {lid}")
        elif lid not in lines:
            orphans.append(f"row {i}: {lid}")
        else:
            by_id[lid].append(r)
    if leaked:
        rep.add("FAIL", "csv-withheld", f"withheld IDs priced in lineitems.csv: {clip(leaked)}")
    if orphans:
        rep.add("FAIL", "csv-orphans", f"line_id not in takeoff.md: {clip(orphans)}")
    if untraced:
        rep.add("WARN", "csv-untraced", f"non-Div-01 lines with no line_id: {clip(untraced)}")

    mism, prov = [], []
    for lid, rs in by_id.items():
        t = lines[lid]
        same_unit = [r for r in rs if r.get("unit", "").strip().upper() == t["unit"]]
        if t["qty"] is not None and same_unit:
            qs = [num(r.get("qty")) or 0.0 for r in same_unit]
            tol = max(abs(t["qty"]) * 0.001, 0.005)
            if not (any(abs(q - t["qty"]) <= tol for q in qs) or abs(sum(qs) - t["qty"]) <= tol):
                mism.append(f"{lid}: takeoff {t['qty']:g} {t['unit']} vs CSV {qs}")
        for r in rs:
            for k in ("method", "confidence"):
                v = norm(r.get(k))
                v = CONF_ALIASES.get(v, v)
                if v and v != t[k]:
                    prov.append(f"{lid}.{k}: CSV {v!r} vs takeoff {t[k]!r}")
    carried = {lid for lid in lines if lines[lid]["qty"] is not None
               and lines[lid]["confidence"] != "rfi"}
    dropped = sorted(carried - set(by_id))
    if mism:
        rep.add("FAIL", "csv-qty", f"CSV qty ≠ takeoff qty (waste belongs in waste_pct): {clip(mism)}")
    if prov:
        rep.add("WARN", "csv-provenance", f"provenance differs from takeoff: {clip(prov)}")
    if dropped:
        rep.add("WARN", "csv-coverage", f"takeoff lines not carried to lineitems.csv: {clip(dropped)}")
    if not (leaked or orphans or mism or dropped):
        rep.add("PASS", "csv-tie-out", f"{len(by_id)} takeoff IDs tie to lineitems.csv")


def check_ratios(lines, gfa, sector, rep):
    def tot(pred):
        return sum(l["qty"] for l in lines.values() if l["qty"] is not None and pred(l))

    def m(pat, l):
        return re.search(pat, l["item"], re.I)

    rebar_lb = (tot(lambda l: m(r"rebar|reinforc", l) and l["unit"] in ("LB", "LBS"))
                + 2000 * tot(lambda l: m(r"rebar|reinforc", l) and l["unit"] in ("TON", "TONS")))
    conc_cy = tot(lambda l: l["div"] == "03" and l["unit"] == "CY" and not m(r"grout", l))
    cmu_ea = tot(lambda l: l["div"] == "04" and l["unit"] == "EA" and m(r"cmu|block", l))
    cmu_sf = tot(lambda l: l["div"] == "04" and l["unit"] == "SF" and m(r"cmu|block|masonry", l))
    tons = tot(lambda l: l["unit"] in ("TON", "TONS") and not m(r"rebar|reinforc|steel", l)
               and (l["div"] == "23" or m(r"hvac|a/?c\b|condens|heat pump|rtu|ahu|split", l)))
    gyp = tot(lambda l: l["div"] == "09" and l["unit"] == "SF"
              and m(r"gyp|drywall|gwb|sheetrock|wallboard", l))

    cands = [("rebar_lb_per_cy", "rebar lb/CY", rebar_lb, conc_cy),
             ("cmu_per_sf", "CMU units/SF wall", cmu_ea, cmu_sf),
             ("sf_per_ton", "SF/ton HVAC", gfa or 0, tons),
             ("gyp_sf_per_gfa", "gyp SF/SF floor", gyp, gfa or 0)]
    ran = 0
    for key, label, a, b in cands:
        if not a or not b:
            continue
        ran += 1
        bands = RATIO_BANDS[key]
        lo, hi = bands.get(sector) or bands.get("*")
        v = a / b
        if lo <= v <= hi:
            rep.add("PASS", "ratio", f"{label} = {v:,.2f} (screen {lo}–{hi})")
        else:
            rep.add("WARN", "ratio", f"{label} = {v:,.2f} outside {lo}–{hi} ({sector}) — "
                                     "explain in 'Quantity reasonableness checks' or fix")
    if not gfa:
        rep.add("INFO", "ratio", "no 'Gross floor area' in header — SF/ton and gyp/GFA skipped")
    if not ran:
        rep.add("INFO", "ratio", "no starred §13 ratio computable from the item names")


def check_golden(path, lines, rep):
    with Path(path).open(newline="", encoding="utf-8-sig") as f:
        gold = [r for r in csv.DictReader(f) if any((v or "").strip() for v in r.values())]
    by_item = {norm(l["item"]): (lid, l) for lid, l in lines.items()}
    passed, warned, failed, errs = 0, [], [], []
    for g in gold:
        gid, gitem = (g.get("id") or "").strip(), (g.get("item") or "").strip()
        want, unit = num(g.get("qty")), (g.get("unit") or "").strip().upper()
        tol = num(g.get("tol_pct")) or 2.0
        hit = lines.get(gid) if gid in lines else (by_item.get(norm(gitem)) or (None, None))[1]
        name = gid or gitem
        if hit is None:
            failed.append(f"{name}: missing from takeoff")
            continue
        if hit["unit"] != unit or hit["qty"] is None or not want:
            failed.append(f"{name}: takeoff {hit['qty']} {hit['unit']} vs golden {want} {unit}")
            continue
        d = (hit["qty"] - want) / want * 100
        errs.append(abs(d))
        if abs(d) <= tol:
            passed += 1
        elif abs(d) <= 2 * tol:
            warned.append(f"{name}: {d:+.2f}% (tol {tol}%)")
        else:
            failed.append(f"{name}: {hit['qty']:g} vs {want:g} {unit} = {d:+.2f}% (tol {tol}%)")
    if failed:
        rep.add("FAIL", "golden", f"regression vs verified quantities: {clip(failed)}")
    if warned:
        rep.add("WARN", "golden", f"within 2× tolerance: {clip(warned)}")
    mae = sum(errs) / len(errs) if errs else 0.0
    rep.add("PASS" if not failed and not warned else "INFO", "golden",
            f"{passed}/{len(gold)} within tolerance; mean |Δ| {mae:.2f}%")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("project_dir")
    ap.add_argument("--sector", default="residential",
                    choices=["residential", "commercial", "ti", "public"])
    ap.add_argument("--golden", default=None, help="CSV of verified quantities to regress against")
    ap.add_argument("--strict", action="store_true", help="exit 1 on WARNs too (CI gate)")
    args = ap.parse_args()
    proj = Path(args.project_dir)
    path = proj / "takeoff.md"
    if not path.exists():
        print(f"FAIL: {path} not found")
        sys.exit(1)
    md = path.read_text(encoding="utf-8", errors="replace")
    secs = sections(md)
    rep = Report()

    check_sections(secs, md, rep)
    index = check_sheet_index(secs, rep)
    scale_log = check_scale_log(secs, rep)
    lines = check_quantities(secs, index, scale_log, rep)
    withheld = check_withheld(secs, lines, rep)
    check_qa(secs, rep)
    check_csv(proj, lines, withheld, rep)
    check_ratios(lines, gross_floor_area(md), args.sector, rep)
    if args.golden:
        check_golden(args.golden, lines, rep)

    print(f"\nvalidate_takeoff — {proj}  (sector={args.sector})\n")
    counts = rep.dump()
    sys.exit(1 if counts["FAIL"] or (args.strict and counts["WARN"]) else 0)


if __name__ == "__main__":
    main()
