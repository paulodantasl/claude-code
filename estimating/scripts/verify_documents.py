#!/usr/bin/env python3
"""Verify that the PUBLISHED numbers in a project's markdown deliverables still
tie to lineitems.csv + markups.csv.

validate_estimate.py checks that the ESTIMATE is internally sound.  This checks
the other half: that every table and figure the client actually reads still
agrees with the estimate it was derived from.

Why this exists
---------------
On job 2026-374 the same failure recurred three times.  A revision changes the
bid; a find-and-replace sweeps the headline figure through the prose; and every
DERIVED table silently keeps its old numbers.  The tables stay plausible -- one
of them stayed perfectly self-consistent three revisions after it went stale,
because its loaded column was still exactly its (old) direct times its (old)
markup factor.  Nothing inside such a table disagrees with anything else inside
it, so no amount of reading it catches the problem.  Worse, a sweep that hits a
table's first and last row but not its middle leaves a waterfall whose endpoints
no longer connect -- and one deliverable shipped a line reading
"Waterfall foots: A + B + C = D" where A+B+C did not equal D.

The lesson is that derived tables must be REGENERATED from source, never
patched -- and that a machine, not a reader, has to confirm it.

Usage
-----
    python3 estimating/scripts/verify_documents.py <project_dir>

Exit status is 1 if any check fails, so it can gate a commit.
"""
from __future__ import annotations

import csv
import re
import sys
from pathlib import Path

# Documents that publish derived numbers.  audit-report.md is deliberately
# excluded: it is a DATED audit of a specific past revision and is supposed to
# carry that revision's figures.
DOCS = [
    "bid-proposal.md",
    "scope-of-work.md",
    "estimate-summary.md",
    "takeoff.md",
    "lease-abstract.md",
    "project-brief.md",
]

# Of those, the ones that actually quote the bid total.  lease-abstract.md
# abstracts the lease and project-brief.md holds a PRIOR third-party GMP as a
# benchmark -- neither publishes our bid, so requiring it there would be a
# manufactured failure rather than a real one.
BID_DOCS = {
    "bid-proposal.md",
    "scope-of-work.md",
    "estimate-summary.md",
    "takeoff.md",
}

# Markup waterfall order -- must match build_estimate_xlsx.py.
WATERFALL = [
    "general_conditions_pct",
    "contingency_pct",
    "insurance_pct",
    "bond_pct",
    "permit_pct",
    "ohp_pct",
]

TOL = 1.0  # dollars; published figures are rounded to whole dollars


class Report:
    def __init__(self) -> None:
        self.fails: list[str] = []
        self.passes = 0

    def check(self, ok: bool, label: str, detail: str = "") -> bool:
        if ok:
            self.passes += 1
            print(f"  [PASS] {label}")
        else:
            self.fails.append(label)
            print(f"  [FAIL] {label}" + (f"\n         {detail}" if detail else ""))
        return ok

    def info(self, label: str) -> None:
        print(f"  [INFO] {label}")


def load_markups(path: Path) -> dict[str, float]:
    out: dict[str, float] = {}
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or line.startswith("key,"):
            continue
        key, _, val = line.partition(",")
        try:
            out[key] = float(val)
        except ValueError:
            continue
    return out


def load_lines(path: Path) -> tuple[float, float, dict[str, float], dict[str, int]]:
    """Return (direct, material_incl_waste, per-division direct, per-division count)."""
    direct = material = 0.0
    by_div: dict[str, float] = {}
    n_div: dict[str, int] = {}
    with path.open() as fh:
        for row in csv.DictReader(fh):
            qty = float(row["qty"] or 0)
            waste = 1 + float(row["waste_pct"] or 0) / 100
            mat = qty * float(row["unit_mat"] or 0) * waste
            rest = qty * (
                float(row["unit_lab"] or 0)
                + float(row["unit_equip"] or 0)
                + float(row["unit_sub"] or 0)
            )
            material += mat
            direct += mat + rest
            div = row["division"]
            by_div[div] = by_div.get(div, 0.0) + mat + rest
            n_div[div] = n_div.get(div, 0) + 1
    return direct, material, by_div, n_div


def run_waterfall(direct: float, material: float, mk: dict[str, float]) -> tuple[list[tuple[str, float, float]], float]:
    """Return ([(label, amount, running)], bid)."""
    steps: list[tuple[str, float, float]] = []
    running = direct
    tax = material * mk.get("material_sales_tax_pct", 0.0) / 100
    running += tax
    steps.append(("material_sales_tax_pct", tax, running))
    for key in WATERFALL:
        amt = running * mk.get(key, 0.0) / 100
        running += amt
        steps.append((key, amt, running))
    return steps, running


def money(text: str) -> list[int]:
    """Every $N,NNN figure in a chunk of markdown, as ints."""
    return [int(m.replace(",", "")) for m in re.findall(r"\$([\d]{1,3}(?:,\d{3})+)", text)]


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__)
        return 2
    proj = Path(sys.argv[1])
    if not proj.is_dir():
        print(f"not a directory: {proj}")
        return 2

    rep = Report()
    direct, material, by_div, n_div = load_lines(proj / "lineitems.csv")
    mk = load_markups(proj / "markups.csv")
    steps, bid = run_waterfall(direct, material, mk)
    n_rows = sum(n_div.values())

    print(f"\n  Source of truth: direct ${direct:,.0f} (material ${material:,.0f}) "
          f"over {n_rows} rows -> BID ${bid:,.0f}\n")

    present = {d: (proj / d) for d in DOCS if (proj / d).exists()}
    texts = {d: p.read_text() for d, p in present.items()}

    # ---- 1. every document carries the current bid --------------------------
    bid_str = f"${bid:,.0f}"
    for doc, text in texts.items():
        if doc not in BID_DOCS:
            rep.info(f"{doc} does not quote the bid total - skipped")
            continue
        rep.check(bid_str in text, f"{doc} publishes the current bid {bid_str}")

    # ---- 2. published waterfall tables tie ----------------------------------
    # A waterfall row looks like: | <label> | **N.N%** | <base> | $amount | $running |
    want = {
        "material_sales_tax_pct": steps[0],
        "contingency_pct": next(s for s in steps if s[0] == "contingency_pct"),
        "insurance_pct": next(s for s in steps if s[0] == "insurance_pct"),
        "ohp_pct": next(s for s in steps if s[0] == "ohp_pct"),
    }
    label_pat = {
        "material_sales_tax_pct": r"sales tax",
        "contingency_pct": r"[Cc]ontingency",
        "insurance_pct": r"[Ii]nsurance",
        "ohp_pct": r"[Oo]verhead",
    }
    for doc, text in texts.items():
        for key, (_, amount, running) in want.items():
            rows = []
            for ln in text.splitlines():
                # A waterfall row is exactly: | label | **N.N%** | base | $amt | $running |
                cells = [c.strip() for c in ln.strip().strip("|").split("|")]
                if len(cells) != 5:
                    continue
                if not re.fullmatch(r"\*{0,2}\d+\.\d%\*{0,2}", cells[1]):
                    continue
                if not re.search(label_pat[key], cells[0]):
                    continue
                rows.append(ln)
            for ln in rows:
                vals = money(ln)
                if len(vals) < 2:
                    continue
                got_amt, got_run = vals[-2], vals[-1]
                ok = abs(got_amt - amount) <= TOL and abs(got_run - running) <= TOL
                rep.check(
                    ok,
                    f"{doc} waterfall row '{key}'",
                    f"published ${got_amt:,} / running ${got_run:,}; "
                    f"expected ${amount:,.0f} / ${running:,.0f}",
                )

    # ---- 3. published division tables sum to direct -------------------------
    # Long form:  | 26 | Electrical | 38 | $152,595 | 18.7% | ...
    # Short form: | 26 Electrical | $152,595 | 18.7% |
    for doc, text in texts.items():
        long_rows = re.findall(r"^\| (\d{2}) \| [^|]+ \| (\d+) \| \$([\d,]+) \|", text, re.M)
        if long_rows:
            total = sum(int(v.replace(",", "")) for _, _, v in long_rows)
            count = sum(int(c) for _, c, _ in long_rows)
            rep.check(abs(total - direct) <= len(long_rows),
                      f"{doc} division table sums to direct",
                      f"table ${total:,} vs source ${direct:,.0f}")
            rep.check(count == n_rows,
                      f"{doc} division table row counts match",
                      f"table {count} vs source {n_rows}")
        short_rows = re.findall(r"^\| (\d{2}) [^|]+ \| \$([\d,]+) \| ([\d.]+)% \|", text, re.M)
        if short_rows:
            total = sum(int(v.replace(",", "")) for _, v, _ in short_rows)
            pct = sum(float(p) for _, _, p in short_rows)
            rep.check(abs(total - direct) <= len(short_rows),
                      f"{doc} short division table sums to direct",
                      f"table ${total:,} vs source ${direct:,.0f}")
            rep.check(abs(pct - 100.0) <= 1.0,
                      f"{doc} short division table percentages foot to 100",
                      f"{pct:.1f}%")

    # ---- 4. any "A + B + ... = C" claim actually adds up --------------------
    add_claim = re.compile(
        r"((?:\$[\d,]+(?:\s*[+]\s*))+\$[\d,]+)\s*=\s*\*{0,2}\$([\d,]+)"
    )
    for doc, text in texts.items():
        for m in add_claim.finditer(text):
            parts = [int(x.replace(",", "")) for x in re.findall(r"\$([\d,]+)", m.group(1))]
            claimed = int(m.group(2).replace(",", ""))
            line_no = text[: m.start()].count("\n") + 1
            rep.check(abs(sum(parts) - claimed) <= TOL,
                      f"{doc}:{line_no} arithmetic claim foots",
                      f"{' + '.join(f'${p:,}' for p in parts)} = ${sum(parts):,}, "
                      f"but published ${claimed:,}")

    # ---- 4b. was / now / delta rows are self-consistent ---------------------
    # Shape: | label | $old | $new | +$delta (+N.N%) |
    # This is how the prior-GMP reconciliation went stale: the "now" column was
    # swept forward by a find-and-replace and the delta column was not, so the
    # row published a delta against a bid that no longer existed.  It survived
    # check 4 because it is a table row, not an "A + B = C" sentence.
    wnd = re.compile(
        r"^\|[^|]+\|[^$|]*\$([\d,]+)[^|]*\|[^$|]*\$([\d,]+)[^|]*\|"
        r"[^|]*?([+\-−])\$([\d,]+)\s*\(([+\-−])([\d.]+)%\)",
        re.M,
    )
    for doc, text in texts.items():
        for m in wnd.finditer(text):
            old = int(m.group(1).replace(",", ""))
            new = int(m.group(2).replace(",", ""))
            sign = -1 if m.group(3) in "-−" else 1
            delta = sign * int(m.group(4).replace(",", ""))
            psign = -1 if m.group(5) in "-−" else 1
            pct = psign * float(m.group(6))
            line_no = text[: m.start()].count("\n") + 1
            ok_d = abs((new - old) - delta) <= TOL
            ok_p = old and abs((new - old) / old * 100 - pct) <= 0.15
            rep.check(ok_d and ok_p,
                      f"{doc}:{line_no} was/now/delta row is self-consistent",
                      f"${old:,} -> ${new:,} is {new - old:+,} ({(new - old) / old * 100:+.1f}%); "
                      f"published {delta:+,} ({pct:+.1f}%)")

    # ---- 5. derived scenario figures are recomputed, not stale --------------
    # Deliberately EXACT, not heuristic.  An earlier version of this check
    # flagged "any 7-figure value near the bid", which cannot tell a stale
    # figure from a legitimately different quantity (an all-alternates total,
    # a sensitivity scenario, the old value in a was/now row) and produced
    # mostly false positives -- the same parse-manufactures-a-gap failure the
    # protocol's guard #22 is about.  So: only relationships we can state.
    scenarios = {
        # (contingency, insurance, bond) -> published bid must equal this
        (10.0, mk.get("insurance_pct", 0.0), 0.0): None,
        (10.0, 0.6, 0.0): None,
        (mk.get("contingency_pct", 0.0), mk.get("insurance_pct", 0.0), 1.5): None,
    }
    for (cont, ins, bond) in list(scenarios):
        alt = dict(mk)
        alt["contingency_pct"], alt["insurance_pct"], alt["bond_pct"] = cont, ins, bond
        _, val = run_waterfall(direct, material, alt)
        scenarios[(cont, ins, bond)] = val

    # A sensitivity row carries its two rates and its resulting bid.
    for doc, text in texts.items():
        for ln in text.splitlines():
            if not ln.startswith("|") or "%" not in ln:
                continue
            rates = [float(x) for x in re.findall(r"(\d+\.\d)%", ln)]
            vals = money(ln)
            if len(rates) < 2 or not vals:
                continue
            cont, ins = rates[0], rates[1]
            bond = 1.5 if len(rates) > 2 and abs(rates[2] - 1.5) < 0.01 else 0.0
            key = (cont, ins, bond)
            if key not in scenarios:
                continue
            line_no = text.splitlines().index(ln) + 1
            rep.check(any(abs(v - scenarios[key]) <= TOL for v in vals),
                      f"{doc}:{line_no} sensitivity row ({cont}%/{ins}%"
                      + (f"/{bond}% bond" if bond else "") + ")",
                      f"published {[f'${v:,}' for v in vals]}; "
                      f"expected ${scenarios[key]:,.0f}")

    print(f"\n  Summary: {len(rep.fails)} FAIL / {rep.passes} PASS\n")
    if rep.fails:
        print("  Derived tables must be REGENERATED from lineitems.csv + markups.csv,")
        print("  never patched in place. See guard #28 in the takeoff protocol.\n")
    return 1 if rep.fails else 0


if __name__ == "__main__":
    sys.exit(main())
