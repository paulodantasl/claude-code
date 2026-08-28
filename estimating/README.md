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

### Escalation check (`--escalation`)

The validator can check the carried `contingency_pct` against the trailing move in a
published material price index, so an escalation allowance is defended by a cited
series instead of asserted:

```
python estimating/scripts/validate_estimate.py estimating/projects/<slug>/ \
    --sector commercial --escalation --bid-validity-days 60
```

It scales the index move by this bid's material share of direct cost and by the days
the price is held, then compares that to the contingency line. It WARNs when
escalation alone would consume the line, and cites the series and both endpoint
observations so a reviewer can trace the number.

Opt-in and advisory by design: it never FAILs, and without `ideal_apis`, an
`IDEAL_FRED_KEY`, or network it reports why it was skipped — so the default run stays
a deterministic offline gate. Bid validity comes from `--bid-validity-days`, else a
`bid_validity_days` row in `markups.csv`, else 30 days.

Requires the [`ideal_apis`](../ideal_apis/README.md) client (`pip install -e ideal_apis`)
and a free key from fred.stlouisfed.org.

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
