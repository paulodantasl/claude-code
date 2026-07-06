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

These live in `.claude/agents/`. Claude routes to them automatically when you describe a
task, or invoke the whole pipeline with the `/bid` command (`.claude/commands/bid.md`).

## Quick start
```
/bid Acme Distribution Center, Orlando FL        # auto-detects sector
/bid-public | /bid-residential | /bid-commercial | /bid-ti   # sector-tuned
```
…or just ask: *"Take off the structural concrete from these plans and price it."*

Per-project files live in `estimating/projects/<slug>/` — see that folder's README for
the layout.

## Knowledge base (`estimating/reference/`)
The agents read these for Florida-precise, consistent results:
- `florida-code.md` — HVHZ, FBC, wind/flood, NOA/FL#, termite, threshold, sales tax, bonds, soils.
- `csi-divisions.md` — MasterFormat division map + the scope-gap checklist that prevents holes/double-counts between trades.
- `estimating-methodology.md` — units, labor burden, waste factors, General Conditions, the markup waterfall, and reasonableness checks.
- `takeoff-accuracy-protocol.md` / `estimating-accuracy-protocol.md` — **mandatory accuracy gates** (plan-graphics-govern, two-direction recounts, full-schedule reads, benchmark bands, scope↔estimate tie-out, zero-qty guards) encoding real observed failure modes.
- `sector-public-bidding.md` / `sector-residential-new.md` / `sector-commercial-new.md` / `sector-tenant-improvement.md` — **market-sector profiles** (what changes per pipeline stage, division emphasis, markup posture, red flags). Invoked by `/bid-public`, `/bid-residential`, `/bid-commercial`, `/bid-ti`, or auto-detected by `/bid`.

## Templates (`estimating/templates/`)
Deliverable skeletons for takeoff, scope, estimate-workbook schema, proposal, procurement,
the audit checklist, and the loan-package config (`loan-package-config.template.json`).

## Workbook builder (`estimating/scripts/build_estimate_xlsx.py`)
Turns `lineitems.csv` + `markups.csv` into a formula-driven `estimate.xlsx` (Detail +
Summary sheets, division subtotals, full markup waterfall). Requires `openpyxl`
(in `requirements.txt`):
```
python3 estimating/scripts/build_estimate_xlsx.py estimating/projects/<slug>/   # + estimate-summary.md
python3 estimating/scripts/validate_estimate.py estimating/projects/<slug>/ --sector <sector>   # deterministic QA
python3 estimating/scripts/build_loan_package_xlsx.py estimating/projects/<slug>/   # 13-tab bank loan package (/loan-package)
```

## Source of truth & sync topology

`estimating/{reference,templates,scripts}` are **canonical**. Every same-named file
under `plugins/construction-estimating/` (plugin `reference/ templates/ scripts/`,
each skill's `resources/`, `claude-ai-project/knowledge/`) is a **generated copy** —
never hand-edit a copy. After editing a canonical file run
`python3 estimating/scripts/sync_plugin.py --write`, and run `--check` before any
commit (agents/ and commands/ under the plugin are intentionally path-adapted and NOT
synced; `claude-ai-project/PROJECT_INSTRUCTIONS.md` and `deliverable-templates.md` are
chat transforms maintained by hand). The Claude.ai Project knowledge does NOT update
from git — re-upload changed knowledge files there after each release.

## Important limits (read this)
- **Costs are budgetary assumptions**, not quotes, until backed by real vendor/sub
  pricing. The estimator labels plugs/allowances; confirm them before submitting.
- **Quantities scaled off raster PDFs are approximate.** The takeoff flags them and
  recommends a verified measured takeoff (Bluebeam/PlanSwift/etc.) before final pricing.
- The agents **default to Florida** and confirm the actual AHJ from the documents; tell
  them if a job is elsewhere.
- Real plan sets and proprietary pricing under `estimating/projects/` are **git-ignored**
  by default (only the README is tracked). Don't commit confidential bid data.
