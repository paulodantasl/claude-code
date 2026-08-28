# Florida Construction Precon Agent Team

A team of Claude Code subagents that perform **quantity takeoff**, **executive scope of
work**, **cost estimating**, **bid proposals**, and **independent audit / verification /
validation** for construction bids — defaulted to **Florida** (HVHZ, FBC, wind, flood,
NOA/FL# products, termite, sales tax, bonds). Works at general-contractor (whole-building)
or specialty-subcontractor level, from PDF plan sets/specs and/or digitized takeoff
exports.

This complements the lead-generation side of the repo (`permit_scraper/`,
`planhub_gc_scraper.py`): find the work → **bid the work**.

## The team

| Subagent | Role | Output |
|----------|------|--------|
| `takeoff-engineer` | Quantities by CSI division from PDFs; validates digitized exports | `takeoff.md` |
| `scope-writer` | Executive scope — inclusions/exclusions/clarifications/alternates/VE | `scope-of-work.md` |
| `cost-estimator` | Prices the takeoff; builds the Excel workbook | `lineitems.csv`, `markups.csv`, `estimate.xlsx` |
| `bid-proposal-writer` | Client/GC-facing proposal & cover letter | `bid-proposal.md` |
| `estimate-auditor` | Independent QA of any/all of the above, or third-party work | `audit-report.md` |
| `procurement-specialist` | **Live** material sourcing — real suppliers, current price, availability, lead time (FL#/NOA aware); cites every source | `procurement.md`, `procurement.csv` |

These live in `.claude/agents/`, and are mirrored into the portable plugin bundle at
`plugins/construction-estimating/`. Claude routes to them automatically when you describe
a task, or invoke the whole pipeline with the `/bid` command (`.claude/commands/bid.md`).

To use them **outside this repo** — in any folder on your machine, or in claude.ai /
Cowork chat — see **[INSTALL.md](INSTALL.md)**.

## Quick start
```
/bid Acme Distribution Center, Orlando FL        # auto-detects sector
/bid-public | /bid-residential | /bid-commercial | /bid-ti   # sector-tuned
```
…or run a single stage on demand:
```
/takeoff  /scope  /estimate  /proposal  /audit  /procure  /loan-package
```
…or just ask: *"Take off the structural concrete from these plans and price it."*

Per-project files live in `estimating/projects/<slug>/` — see that folder's README for
the layout.

## Maintaining the copies
`estimating/{reference,templates,scripts}` is canonical; the plugin bundle, the 8 skills,
and `.claude/skills/` are derived from it. After editing canonical, run:
```
python3 estimating/sync.py --write     # regenerate derived copies (--check to gate)
```

## Knowledge base (`estimating/reference/`)
The agents read these for Florida-precise, consistent results:
- `florida-code.md` — HVHZ, FBC, wind/flood, NOA/FL#, termite, threshold, sales tax, bonds, soils.
- `csi-divisions.md` — MasterFormat division map + the scope-gap checklist that prevents holes/double-counts between trades.
- `estimating-methodology.md` — units, labor burden, waste factors, General Conditions, the markup waterfall, and reasonableness checks.
- `takeoff-accuracy-protocol.md` / `estimating-accuracy-protocol.md` — **mandatory accuracy gates** (plan-graphics-govern, two-direction recounts, full-schedule reads, benchmark bands, scope↔estimate tie-out, zero-qty guards) encoding real observed failure modes.
- `sector-public-bidding.md` / `sector-residential-new.md` / `sector-commercial-new.md` / `sector-tenant-improvement.md` — **market-sector profiles** (what changes per pipeline stage, division emphasis, markup posture, red flags). Invoked by `/bid-public`, `/bid-residential`, `/bid-commercial`, `/bid-ti`, or auto-detected by `/bid`.

## Templates (`estimating/templates/`)
Deliverable skeletons for takeoff, scope, estimate-workbook schema, proposal, and the
audit checklist.

## Workbook builder (`estimating/scripts/build_estimate_xlsx.py`)
Turns `lineitems.csv` + `markups.csv` into a formula-driven `estimate.xlsx` (Detail +
Summary sheets, division subtotals, full markup waterfall). Requires `openpyxl`
(in `requirements.txt`):
```
python estimating/scripts/build_estimate_xlsx.py estimating/projects/<slug>/
python estimating/scripts/validate_estimate.py estimating/projects/<slug>/ --sector <sector>   # deterministic QA
```

### Escalation check (automatic)

Every validator run checks the carried `contingency_pct` against the trailing move in
a published material price index, so an escalation allowance is defended by a cited
series instead of asserted. No flag, no API key, and no network are needed at
validation time — it reads `estimating/data/escalation.json`, a snapshot refreshed on
a schedule:

```
                 monthly (or on demand)              every run, offline
  FRED  ──────▶  refresh_escalation.py  ──────▶  escalation.json  ──────▶  validate_estimate.py
                 (needs IDEAL_FRED_KEY)           (committed)              (needs nothing)
```

The `escalation-monitor` workflow runs `refresh_escalation.py` monthly, commits the
refreshed snapshot, and opens an issue when a cost-driving series moves faster than
the alert threshold — so a price swing reaches you without anyone thinking to look.

**Setup:** add a free [FRED key](https://fred.stlouisfed.org/docs/api/api_key.html) as
the `IDEAL_FRED_KEY` repository secret. Until the first refresh runs, the validator
reports one INFO row saying the snapshot is missing and carries on. No placeholder
data ships — see [`estimating/data/README.md`](./data/README.md).

**Reading the output.** It scales the index move by this bid's material share of
direct cost and by the days the price is held, then compares that to the contingency
line. It WARNs when escalation alone would consume the line, and cites the series and
both endpoint observations so a reviewer can trace the number:

```
[INFO] escalation: material exposure 22% of direct × +26.0% drift over a 365-day bid
       validity ⇒ 5.81% of bid. WPU081 2025-08-01 100.0 → 2026-08-01 126.0 (+26.0%/yr)
[WARN] escalation: escalation alone needs ~5.81% but contingency_pct is 3.00% — the
       line is fully consumed with nothing left for scope risk
```

Advisory by design: it WARNs, never FAILs, because it rests on a national index rather
than this project's buyout. A snapshot older than 60 days WARNs before its number is
used — PPI publishes monthly.

**Manual runs and overrides:**

```
python3 estimating/scripts/refresh_escalation.py              # refresh the snapshot
python3 estimating/scripts/validate_estimate.py <proj> --escalation-live    # skip the snapshot, query FRED
python3 estimating/scripts/validate_estimate.py <proj> --no-escalation      # skip the check
python3 estimating/scripts/validate_estimate.py <proj> --escalation-series lumber_wood \
                                                       --bid-validity-days 60
```

Bid validity comes from `--bid-validity-days`, else a `bid_validity_days` row in
`markups.csv`, else 30 days.

Requires the [`ideal_apis`](../ideal_apis/README.md) client for the *refresh* step only.

Tests: `python3 -m pytest estimating/tests/`

## Important limits (read this)
- **Costs are budgetary assumptions**, not quotes, until backed by real vendor/sub
  pricing. The estimator labels plugs/allowances; confirm them before submitting.
- **Quantities scaled off raster PDFs are approximate.** The takeoff flags them and
  recommends a verified measured takeoff (Bluebeam/PlanSwift/etc.) before final pricing.
- The agents **default to Florida** and confirm the actual AHJ from the documents; tell
  them if a job is elsewhere.
- Real plan sets and proprietary pricing under `estimating/projects/` are **git-ignored**
  by default (only the README is tracked). Don't commit confidential bid data.
