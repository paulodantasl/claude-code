---
description: Run the preconstruction pipeline for a new residential construction (Florida) — sector-tuned gates over the standard /bid flow.
argument-hint: <project name, or path to a folder of plans/specs>
allowed-tools: Agent, Read, Write, Edit, Bash, Grep, Glob
---

Drive the construction preconstruction pipeline for: **$ARGUMENTS**

**Market sector: new residential construction (Florida).** This command is the standard `/bid` pipeline (takeoff →
optional procurement → scope → estimate → proposal → audit) with the sector profile
applied. You are the precon coordinator — orchestrate the specialist subagents; do not do
their work yourself.

0. **Sector setup.** Read `estimating/reference/sector-residential-new.md` yourself, and pass its path to EVERY subagent
   you delegate to (takeoff-engineer, procurement-specialist, scope-writer, cost-estimator,
   bid-proposal-writer, estimate-auditor) with the instruction to apply its
   pipeline-stage changes, division emphasis, and markup/commercial posture.

1–7. **Follow the `/bid` pipeline steps** (project folder under `estimating-projects/<slug>/`,
   takeoff, optional live procurement, scope, estimate + workbook, proposal, independent
   audit, report back) — with these sector gates enforced on top:

- **Code path:** confirm FBC-Residential vs FBC-Building applicability up front (stories/type edge cases).
- **Lender alignment:** structure the estimate + SOV so it maps to the construction-loan draw schedule; the loan-package builder (`build_loan_package_xlsx.py`) is the standard closing deliverable.
- **Selections discipline:** every owner-selection is an ALLOW line with a cap and a reconciliation rule — allowance creep is the classic residential margin-killer.
- **FL envelope items:** impact/NOA openings, flood (zone/BFE/vents), termite, energy testing (blower door + duct leakage) all priced, never assumed away.

Validator: the cost-estimator and auditor must run
`python3 estimating/scripts/validate_estimate.py <project_dir>/ --sector residential`
and clear every FAIL before the bid is declared ready.
