---
description: Quantity takeoff only — measure/count by CSI division from plans, specs, or a digitized export.
argument-hint: <plan set path, project name, or what to take off>
allowed-tools: Agent, Read, Write, Edit, Bash, Grep, Glob
---

Produce a construction quantity takeoff for: **$ARGUMENTS**

Delegate to the `takeoff-engineer` subagent — do not do the measuring yourself. It carries
the accuracy protocol, the CSI division map, and the Florida code reference, and it knows
where its own knowledge base lives.

1. **Locate the inputs.** Plan PDFs, spec sections, and/or digitized takeoff exports
   (Bluebeam, PlanSwift, STACK, On-Screen Takeoff). If nothing was provided, ask the user
   for the plan set and the jurisdiction/AHJ before proceeding. **Default Florida.**
2. **Set the project folder.** Deliverables go under `estimating-projects/<slug>/` in the
   current working directory (or `estimating/projects/<slug>/` when working inside the
   toolkit repo). Never write into the plugin or skill folder — it is replaced on update.
3. **Pass the sector if known** (public / residential / commercial / tenant-improvement) so
   the agent applies the matching profile. If the sector is obvious from the documents, say
   so; if ambiguous, ask once.
4. **Delegate.** The agent produces `takeoff.md` (quantities by division — each line with
   qty, unit, source sheet, method, confidence flag) plus a seed `lineitems.csv` with cost
   columns blank, ready for pricing.

When it returns, report: quantity highlights by division, the reasonableness ratio checks,
every RFI raised, and which lines are `approx` (scaled, not printed). State plainly that
scaled quantities are assumptions to confirm — do not present them as measured.

This is the takeoff stage only. Pricing is `/estimate`, narrative is `/scope`, and the full
pipeline is `/bid`.
