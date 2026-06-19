# Construction Estimating

A team of Claude Code subagents for **construction takeoff, executive scope of work, cost
estimating, bid proposals, independent QA/audit, and bank construction-loan packages** —
defaulted to **Florida** (HVHZ/FBC/wind/flood/NOA/termite/sales tax), organized by **CSI
MasterFormat**, with **formula-driven Excel** output.

Works at general-contractor (whole-building) or specialty-subcontractor level, from PDF
plan sets/specs and/or digitized takeoff exports (Bluebeam, PlanSwift, STACK, On-Screen).

## Install

```
/plugin marketplace add paulodantasl/claude-code
/plugin install construction-estimating@claude-code-plugins
```

Then, in **any** project folder, run `/bid` or just describe the task (e.g. *"take off the
structural concrete from these plans and price it"*). Updates: `/plugin marketplace update claude-code-plugins`.

> **Dependency:** the Excel builders need `openpyxl` → `pip install openpyxl`.

## What's inside

**Subagents** (auto-routed when you describe a task)

| Agent | Role | Output |
|-------|------|--------|
| `takeoff-engineer` | Quantities by CSI division from PDFs; validates digitized exports | `takeoff.md` |
| `scope-writer` | Executive scope — inclusions/exclusions/clarifications/alternates/VE | `scope-of-work.md` |
| `cost-estimator` | Prices the takeoff; builds the Excel workbook | `lineitems.csv`, `markups.csv`, `estimate.xlsx` |
| `bid-proposal-writer` | Client/GC-facing proposal & cover letter | `bid-proposal.md` |
| `estimate-auditor` | Independent QA of the above, or third-party work | `audit-report.md` |

**Command** — `/bid <project>` runs the full precon pipeline (takeoff → scope → estimate → proposal → audit).

**Knowledge base** (`reference/`) — Florida code (HVHZ, FBC, wind/flood, NOA/FL#, termite,
threshold, sales tax, soils), CSI division + scope-gap guide, estimating methodology
(units, labor burden, waste, GCs, markup waterfall, sanity checks).

**Templates** (`templates/`) — deliverable skeletons + the estimate-workbook & loan-package
config schemas.

**Scripts** (`scripts/`)
- `build_estimate_xlsx.py <project_dir>` → formula-driven estimate workbook (Detail + Summary, division subtotals, markup waterfall).
- `build_loan_package_xlsx.py <project_dir>` → 13-tab bank construction-loan package (Cover, Inputs control panel, Executive Summary, Sources & Uses, Budget Summary + Detail, AIA G703 Schedule of Values, monthly Draw Schedule, Gantt Timeline, Scope, Allowances, Alternates + Unit Prices, Documents Checklist). Logo optional/configurable.

## Where your work goes

Project deliverables are written to your **current working directory** under
`estimating-projects/<project-slug>/` — never inside the plugin (it is replaced on update).
The agents read their knowledge base from `${CLAUDE_PLUGIN_ROOT}` (resolved automatically).

A typical project folder:

```
estimating-projects/<slug>/
├── plans/        # your input PDFs (plans, specs)
├── digitized/    # optional CSV/XLSX takeoff exports
├── logo.png      # optional — your company logo for the loan package
├── loan-package-config.json   # copy from templates/loan-package-config.template.json
├── takeoff*.md   scope-of-work.md   audit-report.md
├── lineitems.csv   markups.csv
├── estimate.xlsx   construction-loan-package.xlsx
```

## Important limits

- **Costs are budgetary assumptions**, not quotes, until backed by real vendor/sub pricing — the estimator labels plugs/allowances.
- **Quantities scaled off raster PDFs are approximate** — the takeoff flags them; get a verified measured takeoff before final pricing.
- The agents **default to Florida** and confirm the actual AHJ from the documents; tell them if a job is elsewhere. (For frequent out-of-state work, swap in a local `reference/` code file.)
- Don't commit confidential bid data — keep `estimating-projects/` out of shared repos.
