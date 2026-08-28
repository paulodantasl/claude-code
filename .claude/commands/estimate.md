---
description: Price a takeoff into a formula-driven Excel estimate workbook — costs, markups, GCs, bonds, FL sales tax.
argument-hint: <project name or path to the project folder>
allowed-tools: Agent, Read, Write, Edit, Bash, Grep, Glob
---

Build the cost estimate for: **$ARGUMENTS**

Delegate to the `cost-estimator` subagent — it carries the estimating methodology, the
accuracy protocol, and the workbook builder, and knows where its knowledge base lives.

1. **Locate the takeoff.** `lineitems.csv` and `takeoff.md` in the project folder. If there
   is no takeoff, run `/takeoff` first — do not price quantities that were never measured.
2. **Choose the pricing basis.** If `procurement.csv` exists (from `/procure`), use those
   sourced prices in place of budgetary plugs. Otherwise the numbers are **budgetary** —
   label them that way in the output and never present them as quotes.
3. **Pass the sector if known** (public / residential / commercial / tenant-improvement) so
   the agent applies the matching markup and General Conditions posture.
4. **Delegate.** The agent fills unit costs in `lineitems.csv`, writes `markups.csv`
   (General Conditions, overhead, profit, bond, insurance, permit, Florida sales tax on
   materials), and runs the builder to produce `estimate.xlsx` — Detail + Summary, live
   formulas, no hardcoded totals.
5. **Run the validator.** The agent must run the bundled `validate_estimate.py` against the
   project folder with the matching `--sector` flag and clear every FAIL. Report the WARNs.

When it returns, report: the bid total, $/SF if the area is known, cost by division, the
validator result, and every plug, allowance, and placeholder the user still has to resolve.

This is the pricing stage only. Run `/audit` before the number goes out the door, and
`/bid` for the full pipeline.
