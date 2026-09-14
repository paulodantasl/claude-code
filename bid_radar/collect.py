"""
Bid Radar collector — orchestrates every Tampa source.

Runs each collector in `bid_radar/sources/`, scores the signals, filters to the
eight tracked submarkets and writes:

    bid_radar/data/signals.jsonl        one scored signal per line
    bid_radar/data/summary.md           what a human reads on Monday morning
    bid_radar/data/abt_directory.csv    Active licensed venues in our
                                        submarkets, with contact details

Runs in GitHub Actions; the Claude sandbox cannot reach the host (PLAN.md §0).
One source failing does not stop the others — an outage on one layer should
cost that section of the report, not the report.
"""
from __future__ import annotations

import csv
import json
import os
import sys
import traceback
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import arcgis  # noqa: E402
import enrich  # noqa: E402
import geo  # noqa: E402
import score as scoring  # noqa: E402
import sources  # noqa: E402
from sources import abt as abt_source  # noqa: E402
from sources.permits import to_signal  # noqa: E402,F401  (re-exported for tests)

DAYS_BACK = int(os.environ.get("DAYS_BACK", "365"))
HEADLINE_DAYS = int(os.environ.get("HEADLINE_DAYS", "90"))
DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
RETRIEVED_AT = datetime.now(timezone.utc).isoformat(timespec="seconds")

TRADE_ORDER = ["medical", "restaurant", "hospitality", "retail", "office", "other"]

# Stages a human can act on, most urgent first. Anything else is history.
LIVE_STAGES = ["early_start", "strip_out", "cra_awarded", "abt", "pre_permit", "revision"]

STAGE_BLURB = {
    "early_start": "The city released interior non-structural work while the main "
                   "permit is still in review. The rest of the scope is being bought out now.",
    "strip_out": "The lease space is being emptied and the record says the build-back "
                 "comes under a separate permit. Committed tenant, unbid fitout.",
    "cra_awarded": "CRA grant money is committed and the work is not finished. "
                   "The only source here with a real dollar figure.",
    "abt": "A wet-zoning record moved — new, newly placarded, or newly Active. "
           "The one source that comes with a phone number.",
    "pre_permit": "A live rezoning, variance or special-use case with a hearing date. "
                  "The earliest signal we have; no tenant named yet.",
    "revision": "A change to an in-flight permit. The job is active.",
}


def scored(signal: dict) -> dict:
    signal.update(scoring.score(signal))
    return signal


def market_share(signals: list[dict]) -> list[dict]:
    """Contractor of record x submarket, from the enriched permits.

    This is the win-rate dataset. PLAN.md Phase 4 wanted it from the
    Hillsborough Clerk's Notices of Commencement; the Clerk's public-records
    hosts refuse cloud traffic, and the Accela record page names the same
    contractor with a licence number attached.
    """
    rows: dict[tuple[str, str], dict] = {}
    for s in signals:
        gc = s.get("contractor_name")
        if not gc or not s.get("hood") or len(gc) < 3:
            continue
        key = (s["hood"], gc.upper())
        row = rows.setdefault(key, {
            "hood": s["hood"], "hood_label": geo.hood_label(s["hood"]),
            "contractor": gc, "licence": s.get("contractor_licence"),
            "permits": 0, "value_total": 0.0, "with_value": 0,
            "trades": Counter(),
        })
        row["permits"] += 1
        row["trades"][s.get("trade") or "other"] += 1
        if s.get("value_est") and not s.get("value_suspect"):
            row["value_total"] += float(s["value_est"])
            row["with_value"] += 1
        row["licence"] = row["licence"] or s.get("contractor_licence")
    out = []
    for row in rows.values():
        row["avg_value"] = (row["value_total"] / row["with_value"]
                            if row["with_value"] else None)
        row["top_trade"] = row["trades"].most_common(1)[0][0]
        row["trades"] = dict(row["trades"])
        out.append(row)
    return sorted(out, key=lambda r: (-r["permits"], -(r["value_total"] or 0)))


def calibration_seed(signals: list[dict], rows: list[dict]) -> dict | None:
    """A measured prior for the `avgTI` dial, and nothing more.

    The dial has been guessing at $325,000. This replaces the guess with the
    average declared job value of the qualified fitout permits we actually
    observed, per submarket and overall.

    What it is NOT: a win rate. Win rate is a fact about us, and the only place
    it can come from is Won/Lost rows a person logged on the board. Market
    share is a different quantity and must never be written into that dial.
    Nor is a permit's declared job value a contract value — it is what the
    applicant told the city the work is worth. It is the closest measured
    number we have, and the page labels it as the market figure it is.
    """
    usable = [s for s in signals
              if s.get("value_est") and not s.get("value_suspect")
              and s.get("hood") and s.get("qualified")]
    vals = [float(s["value_est"]) for s in usable]
    if not vals:
        return None
    by_hood: dict[str, dict] = {}
    for s in usable:
        h = by_hood.setdefault(s["hood"], {"hood_label": geo.hood_label(s["hood"]),
                                           "n": 0, "value_total": 0.0})
        h["n"] += 1
        h["value_total"] += float(s["value_est"])
    for h in by_hood.values():
        h["avg_value"] = h["value_total"] / h["n"]
    gcs = {r["contractor"] for r in rows}
    return {
        "measures": "avgTI",
        "basis": "declared job value on qualified fitout permits, City of Tampa Accela",
        "window_days": DAYS_BACK,
        "n": len(vals),
        "avg_value": sum(vals) / len(vals),
        "median_value": sorted(vals)[len(vals) // 2],
        "by_hood": by_hood,
        "contractors_seen": len(gcs),
        "retrieved_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }


def write_market_share(rows: list[dict], path: str) -> None:
    cols = ["hood_label", "contractor", "licence", "permits", "top_trade",
            "with_value", "value_total", "avg_value"]
    with open(path, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow(r)


def run_sources(days_back: int) -> tuple[list[dict], dict]:
    """Collect every source. Ids are the §2.2 dedupe key, and a source can
    legitimately return the same record twice — the permit layer carries one
    feature per address unit, so BLD-26-0522346 arrives as both
    `5041 W Cypress St` and `5041 W Cypress St #FS`. Keep the first; they
    would collide on one document id in the tracker anyway."""
    signals: list[dict] = []
    seen: set[str] = set()
    report: dict = {}
    for module in sources.ALL:
        try:
            rows = module.collect(days_back)
            fresh = [r for r in rows if r["id"] not in seen and not seen.add(r["id"])]
            signals.extend(fresh)
            report[module.SOURCE] = {"name": module.NAME, "fetched": len(fresh),
                                     "duplicates": len(rows) - len(fresh)}
            dupes = f" ({len(rows) - len(fresh)} duplicate ids dropped)" if len(rows) != len(fresh) else ""
            print(f"  {module.SOURCE:<12} {len(fresh):>5} records{dupes}", flush=True)
        except Exception as exc:  # noqa: BLE001
            report[module.SOURCE] = {"name": module.NAME, "error": f"{type(exc).__name__}: {exc}"}
            print(f"  {module.SOURCE:<12} FAILED {type(exc).__name__}: {exc}", flush=True)
            traceback.print_exc()
    return signals, report


# --------------------------------------------------------------------- report

def _table(rows: list[dict], *, score_col: bool = True) -> str:
    cols = ["Source", "Ref", "Filed", "Stage", "Submarket", "Trade"]
    if score_col:
        cols.append("Score")
    cols += ["Entity / scope", "Address", "Contact", "Value", "Link"]
    out = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    for s in rows:
        name = (s.get("entity") or s.get("scope") or "—").replace("|", "/")
        if len(name) > 46:
            name = name[:43] + "…"
        contacts = s.get("contacts") or []
        contact = contacts[0]["value"] if contacts else "—"
        if len(contacts) > 1:
            contact += f" (+{len(contacts) - 1})"
        value = f"${s['value_est']:,.0f}" if s.get("value_est") else "—"
        link = f"[record]({s['source_url']})" if s.get("source_url") else "—"
        cells = [s["source"], f"`{s['source_id']}`", s.get("filed_at") or "—",
                 s.get("stage_hint") or "—",
                 geo.hood_label(s["hood"]) if s.get("hood") else "—",
                 s.get("trade") or "—"]
        if score_col:
            cells.append(f"**{s.get('score', 0)}**")
        cells += [name, s.get("address") or "—", contact, value, link]
        out.append("| " + " | ".join(cells) + " |")
    return "\n".join(out)


def _by_score(rows: list[dict]) -> list[dict]:
    return sorted(rows, key=lambda s: (-(s.get("score") or 0), s.get("filed_at") or ""))


def summary(signals: list[dict], report: dict, directory: list[dict] | None = None) -> str:
    tracked = [s for s in signals if s.get("hood")]
    qualified = _by_score([s for s in tracked if s.get("qualified")])
    directory = directory or []

    L: list[str] = []
    L.append("# Tampa Bid Radar")
    L.append("")
    L.append(f"Collected {RETRIEVED_AT} · {DAYS_BACK}-day window · "
             f"eight tracked submarkets")
    L.append("")

    L.append("| Source | Records | In a submarket | Qualified |")
    L.append("|---|---|---|---|")
    for src, info in report.items():
        if src.startswith("_"):
            continue
        if "error" in info:
            L.append(f"| {info['name']} | ⚠️ {info['error']} | — | — |")
            continue
        in_hood = [s for s in tracked if s["source"] == src]
        qual = [s for s in in_hood if s.get("qualified")]
        L.append(f"| {info['name']} | {info['fetched']} | {len(in_hood)} | "
                 f"**{len(qual)}**|")
    L.append(f"| _total_ | {sum(i.get('fetched', 0) for k, i in report.items() if not k.startswith('_'))} | "
             f"{len(tracked)} | **{len(qualified)}** |")
    L.append("")

    # ---- the list ----------------------------------------------------
    L.append(f"## Qualified — call these ({len(qualified)})")
    L.append("")
    L.append(f"Score ≥ {scoring.QUALIFY_AT}/100 with no hard blocker (PLAN §2.3/§2.4), "
             f"inside one of the eight submarkets, bid window still open.")
    L.append("")
    L.append(_table(qualified) if qualified else "_none in this window_")
    L.append("")

    # ---- by stage ----------------------------------------------------
    for stage in LIVE_STAGES:
        rows = _by_score([s for s in tracked if s.get("stage_hint") == stage])
        if not rows:
            continue
        L.append(f"## {stage} ({len(rows)})")
        L.append("")
        L.append(STAGE_BLURB.get(stage, ""))
        L.append("")
        L.append(_table(rows))
        L.append("")

    # ---- grid --------------------------------------------------------
    L.append("## Submarket × trade (live stages only)")
    L.append("")
    live = [s for s in tracked if s.get("stage_hint") in LIVE_STAGES]
    grid: dict[str, Counter] = defaultdict(Counter)
    for s in live:
        grid[s["hood"]][s["trade"]] += 1
    trades = [t for t in TRADE_ORDER if any(g[t] for g in grid.values())]
    if trades:
        L.append("| Submarket | " + " | ".join(trades) + " | total |")
        L.append("|---|" + "---|" * (len(trades) + 1))
        for hood in geo.all_hoods():
            row = grid.get(hood)
            if not row:
                continue
            L.append(f"| {geo.hood_label(hood)} | "
                     + " | ".join(str(row[t] or "") for t in trades)
                     + f" | **{sum(row.values())}** |")
    else:
        L.append("_nothing live in a tracked submarket in this window_")
    L.append("")

    # ---- already awarded --------------------------------------------
    late = _by_score([s for s in tracked if s.get("late") and s.get("is_fitout")])
    if late:
        L.append(f"## Already permitted ({len(late)})")
        L.append("")
        L.append("Not an outreach list. This is who is building what, where — the "
                 "input to win-rate analysis (PLAN Phase 4).")
        L.append("")
        L.append(_table(late[:60], score_col=False))
        if len(late) > 60:
            L.append("")
            L.append(f"_…and {len(late) - 60} more in `signals.jsonl`._")
        L.append("")

    # ---- directory ---------------------------------------------------
    if directory:
        by_hood = Counter(s["hood"] for s in directory)
        L.append(f"## Licensed venue directory ({len(directory)})")
        L.append("")
        L.append("Every **Active** alcoholic-beverage venue inside a tracked "
                 "submarket that publishes a phone or an email. Not leads — a "
                 "prospecting list of the bars and restaurants in our eight "
                 "submarkets, with the owner's own contact details from the "
                 "public record. Full table in `abt_directory.csv`.")
        L.append("")
        L.append("| Submarket | Venues with contact details |")
        L.append("|---|---|")
        for hood in geo.all_hoods():
            if by_hood.get(hood):
                L.append(f"| {geo.hood_label(hood)} | {by_hood[hood]} |")
        L.append("")

    # ---- market share ------------------------------------------------
    share = market_share(signals)
    if share:
        L.append(f"## Who is building fitouts here ({len(share)} contractor × submarket)")
        L.append("")
        L.append("The contractor of record on every enriched permit, from its own "
                 "Accela page. This is the win-rate dataset: the share of this "
                 "table that is ours is our measured share, per submarket. Full "
                 "table in `market_share.csv`.")
        L.append("")
        L.append("| Submarket | Contractor | Licence | Permits | Top trade | Avg job value |")
        L.append("|---|---|---|---|---|---|")
        for r in share[:30]:
            avg = f"${r['avg_value']:,.0f}" if r["avg_value"] else "—"
            L.append(f"| {r['hood_label']} | {r['contractor'][:52]} | "
                     f"{r['licence'] or '—'} | {r['permits']} | {r['top_trade']} | {avg} |")
        L.append("")

    # ---- notes -------------------------------------------------------
    L.append("## What each source can and cannot tell you")
    L.append("")
    L.append("- **Building permits** publish at issuance. There is no application "
             "stage, no valuation, and no applicant or contractor field. Only "
             "`early_start` and `strip_out` rows have a live bid window; the "
             "tenant is parsed from the project description and is blank where it "
             "could not be read with confidence.")
    L.append("- **Active entitlements** are the earliest signal — a live rezoning "
             "or special-use case with a published hearing date — but the layer "
             "names no applicant, so the address is the lead and the trade is "
             "undeclared except on alcoholic-beverage cases.")
    L.append("- **Alcoholic-beverage permits** are the only source with a contact "
             "channel. Seat counts are filled on 23 of 4,096 rows and are not used.")
    en = report.get("_enrich") or {}
    if en and "error" not in en:
        L.append(f"- **Accela enrichment** filled {en.get('enriched', 0)} of "
                 f"{en.get('eligible', 0)} permit rows from their own record pages "
                 f"({en.get('fetched', 0)} fetched this run, {en.get('cached', 0)} "
                 f"from cache, {en.get('failed', 0)} failed). That is where the "
                 f"contractor of record, the job valuation, the real square footage "
                 f"and the applicant's phone and email come from — the ArcGIS layer "
                 f"has none of them.")
    elif en:
        L.append(f"- **Accela enrichment failed** this run: {en.get('error')}. Permit "
                 f"rows will show no valuation and no contact.")
    L.append("- **CRA grants** are the only source with a real dollar figure "
             "(`TOTALPROJECTCOST`); a grant that is Awarded and not Completed has "
             "committed money and outstanding work.")
    L.append("")
    L.append(f"Signals outside every tracked submarket: "
             f"{len(signals) - len(tracked)} of {len(signals)}.")
    return "\n".join(L)


def write_directory(rows: list[dict], path: str) -> None:
    cols = ["hood", "entity", "owner_name", "address", "zip", "phone", "email",
            "sale_type", "occupancy_type", "sqft", "ab_status_at", "source_url"]
    with open(path, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        for s in sorted(rows, key=lambda s: (s["hood"], s.get("entity") or "")):
            contacts = s.get("contacts") or []
            w.writerow({
                "hood": geo.hood_label(s["hood"]),
                "entity": s.get("entity"), "owner_name": s.get("owner_name"),
                "address": s.get("address"), "zip": s.get("zip"),
                "phone": next((c["value"] for c in contacts if c["kind"] == "phone"), ""),
                "email": next((c["value"] for c in contacts if c["kind"] == "email"), ""),
                "sale_type": s.get("sale_type"), "occupancy_type": s.get("occupancy_type"),
                "sqft": s.get("sqft"), "ab_status_at": s.get("ab_status_at"),
                "source_url": s.get("source_url"),
            })


def main() -> int:
    print(f"collecting, {DAYS_BACK}-day window", flush=True)
    signals, report = run_sources(DAYS_BACK)

    # Accela detail changes both the value and the contact components, so it
    # has to land before anything is scored.
    print("\nenriching permits from their Accela record pages", flush=True)
    try:
        report["_enrich"] = enrich.enrich(signals)
        print(f"  {report['_enrich']}", flush=True)
    except Exception as exc:  # noqa: BLE001
        report["_enrich"] = {"error": f"{type(exc).__name__}: {exc}"}
        print(f"  enrichment failed: {exc}", flush=True)

    for s in signals:
        scored(s)

    try:
        directory = abt_source.directory(DAYS_BACK)
        print(f"  directory    {len(directory):>5} active venues with contacts", flush=True)
    except Exception as exc:  # noqa: BLE001
        print(f"  directory    FAILED {type(exc).__name__}: {exc}", flush=True)
        directory = []

    os.makedirs(DATA, exist_ok=True)
    with open(os.path.join(DATA, "signals.jsonl"), "w") as fh:
        for s in _by_score(signals):
            fh.write(arcgis.dumps(s) + "\n")
    if directory:
        write_directory(directory, os.path.join(DATA, "abt_directory.csv"))

    share = market_share(signals)
    if share:
        write_market_share(share, os.path.join(DATA, "market_share.csv"))
        print(f"\nmarket share: {len(share)} contractor x submarket rows", flush=True)
        for r in share[:12]:
            avg = f"avg ${r['avg_value']:,.0f}" if r["avg_value"] else "value unknown"
            print(f"  {r['permits']:>3} {r['hood_label']:<20} {r['contractor'][:44]:<44} {avg}",
                  flush=True)
    seed = calibration_seed(signals, share)
    if seed:
        with open(os.path.join(DATA, "calibration_seed.json"), "w") as fh:
            json.dump(seed, fh, indent=2, default=str)
        print(f"calibration seed: avgTI ${seed['avg_value']:,.0f} "
              f"from {seed['n']} valued permits", flush=True)

    with open(os.path.join(DATA, "summary.md"), "w") as fh:
        fh.write(summary(signals, report, directory) + "\n")

    tracked = [s for s in signals if s.get("hood")]
    qualified = [s for s in tracked if s.get("qualified")]
    print(f"\n{len(signals)} signals · {len(tracked)} in a tracked submarket · "
          f"{len(qualified)} qualified", flush=True)
    for hood, n in Counter(s["hood"] for s in tracked).most_common():
        print(f"  {hood:<12} {n}", flush=True)
    for s in _by_score(qualified)[:25]:
        print(f"  {s['score']:>3} {s['source']:<12} {s['stage_hint']:<12} "
              f"{geo.hood_label(s['hood']):<20} {(s.get('entity') or s.get('scope') or '')[:38]}",
              flush=True)

    failed = [k for k, v in report.items() if "error" in v]
    if failed:
        print(f"\nWARNING: sources failed: {', '.join(failed)}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
