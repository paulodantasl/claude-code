# Projects

One folder per bid: `estimating/projects/<project-slug>/`. Drop the inputs in, run the
pipeline, and the deliverables land alongside them.

```
estimating/projects/<project-slug>/
├── plans/                 # input: PDF plan set(s)        (you provide)
├── specs/                 # input: spec book(s)           (you provide)
├── digitized/             # input: Bluebeam/PlanSwift/STACK exports (CSV/XLSX, optional)
├── takeoff.md             # output: takeoff-engineer
├── scope-of-work.md       # output: scope-writer
├── lineitems.csv          # output: cost-estimator (line items)
├── markups.csv            # output: cost-estimator (markup % config)
├── estimate.xlsx          # output: build_estimate_xlsx.py (formula-driven workbook)
├── bid-proposal.md        # output: bid-proposal-writer
└── audit-report.md        # output: estimate-auditor
```

## Run the whole pipeline
```
/bid <project name or path to plans>
```

## Or invoke a single specialist
Just ask in plain language — Claude routes to the right subagent:
- "Take off the concrete and masonry from the plans in projects/acme-warehouse/plans"
- "Write the scope of work for projects/acme-warehouse"
- "Price the takeoff for acme-warehouse"
- "Audit this third-party estimate" (point it at any CSV/PDF/XLSX)

## Notes
- **Default jurisdiction is Florida.** The agents confirm the AHJ from the documents.
- Quantities scaled off raster PDFs are **approximate** — the takeoff flags them; get a
  verified measured takeoff before final pricing.
- Costs are **budgetary assumptions** until backed by real vendor/subcontractor quotes.
- Real plan sets and proprietary pricing usually shouldn't be committed — see the
  `.gitignore` note in `estimating/README.md`.
