---
description: Run the preconstruction pipeline for a public / government bid (Florida) — sector-tuned gates over the standard /bid flow.
argument-hint: <project name, or path to a folder of plans/specs>
allowed-tools: Agent, Read, Write, Edit, Bash, Grep, Glob
---

Drive the construction preconstruction pipeline for: **$ARGUMENTS**

**Market sector: public / government bid (Florida).** This command is the standard `/bid` pipeline (takeoff →
optional procurement → scope → estimate → proposal → audit) with the sector profile
applied. You are the precon coordinator — orchestrate the specialist subagents; do not do
their work yourself.

0. **Sector setup.** Read `estimating/reference/sector-public-bidding.md` yourself, and pass its path to EVERY subagent
   you delegate to (takeoff-engineer, procurement-specialist, scope-writer, cost-estimator,
   bid-proposal-writer, estimate-auditor) with the instruction to apply its
   pipeline-stage changes, division emphasis, and markup/commercial posture.

1–7. **Follow the `/bid` pipeline steps** (project folder under `estimating-projects/<slug>/`,
   takeoff, optional live procurement, scope, estimate + workbook, proposal, independent
   audit, report back) — with these sector gates enforced on top:

- **Bond posture:** bid bond per the ITB (typ. 5%); P&P bond per FL 255.05 — set `bond_pct` > 0 in markups.csv unless the solicitation waives it. The validator flags `--sector public` with bond at 0.
- **Owner Direct Purchase (ODP):** have the procurement-specialist flag ODP candidates (big-ticket materials the owner buys tax-exempt); the estimator carves the sales tax accordingly.
- **Responsiveness gate:** every addendum acknowledged; the owner's bid form reproduced exactly; unit-price schedule as designed; no qualifications the ITB forbids. A responsive-but-wrong bid loses money; a non-responsive bid is thrown out — the proposal-writer checks both.
- **Certified payroll / Davis-Bacon:** if federal funds are in the project, price the wage determinations and the compliance admin.
- **No post-bid negotiation:** contingency and escalation must be IN the number on bid day.

Validator: the cost-estimator and auditor must run
`python3 estimating/scripts/validate_estimate.py <project_dir>/ --sector public`
and clear every FAIL before the bid is declared ready.
