---
description: Run the full Florida preconstruction pipeline (takeoff → scope → estimate → proposal → audit) for a project.
argument-hint: <project name, or path to a folder of plans/specs>
allowed-tools: Agent, Read, Write, Edit, Bash, Grep, Glob
---

Drive the construction preconstruction pipeline for: **$ARGUMENTS**

You are the precon coordinator. Orchestrate the specialist subagents — do not do their
work yourself. Steps:

0. **Detect the market sector.** From the documents/user: public-government bid →
   `/bid-public` posture (`estimating/reference/sector-public-bidding.md`); new single/multi-family
   residential → `/bid-residential` (`estimating/reference/sector-residential-new.md`); new commercial →
   `/bid-commercial` (`estimating/reference/sector-commercial-new.md`); buildout/TI of existing space →
   `/bid-ti` (`estimating/reference/sector-tenant-improvement.md`). Read the matching profile and pass it
   to every subagent. If ambiguous, ask the user once. Both the estimator and auditor run
   the validator with the matching `--sector` flag.

1. **Set up the project folder.** Under `estimating/projects/<slug>/`, create or locate
   the folder for this project (slugify the name). If the user pointed at plans/specs or a
   folder, move/reference those inputs into it. If little was provided, ask the user for
   the plan set, specs, location/AHJ, and bidding posture (GC vs. specialty trade) before
   proceeding. Confirm the jurisdiction — **default Florida**.

2. **Takeoff** — delegate to the `takeoff-engineer` subagent to produce `takeoff.md`
   (and a seed `lineitems.csv`) from the PDFs and/or to validate any digitized exports.

2a. **(Optional) Live procurement** — if the user wants **real sourced pricing** instead of
   budgetary numbers, delegate to `procurement-specialist` to source each material online
   (suppliers, current price, availability, **lead time**, FL#/NOA) and produce `procurement.md`
   + `procurement.csv`. The cost-estimator then uses these sourced prices in place of budgetary
   plugs. Skip it if the user just wants a fast budgetary number — it is time-intensive.

3. **Scope of work** — delegate to `scope-writer` to produce `scope-of-work.md`,
   reconciled against the takeoff and bid documents.

4. **Estimate** — delegate to `cost-estimator` to build `lineitems.csv` + `markups.csv`
   and run the workbook builder to produce `estimate.xlsx`. Use sourced prices from
   `procurement.csv` if procurement was run (step 2a); otherwise budgetary unit costs.

5. **Proposal** — delegate to `bid-proposal-writer` to produce `bid-proposal.md`,
   numbers tying out to the estimate and scope.

6. **Independent audit** — delegate to `estimate-auditor` to verify everything and write
   `audit-report.md`. **Always run this before declaring the bid ready**, even if earlier
   steps looked clean.

7. **Report back.** Summarize: BID TOTAL, $/SF if known, cost by division, the audit
   verdict, and the open items (RFIs, plugs/allowances, placeholders) the user must
   resolve. List the file paths of every deliverable.

Guidance:
- If the user only wants part of the pipeline (e.g., "just the takeoff" or "audit this
  third-party estimate"), run only the relevant agent(s).
- If the auditor returns Critical or Major findings, surface them prominently and offer to
  loop the relevant agent to fix them, then re-audit.
- Treat all costs and scaled quantities as **assumptions to confirm**, not guarantees.
