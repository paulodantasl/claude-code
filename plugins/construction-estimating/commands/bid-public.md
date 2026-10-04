---
description: Run the preconstruction pipeline for a public / government bid (Florida) — sector-tuned gates over the standard /bid flow.
argument-hint: <project name, or path to a folder of plans/specs>
allowed-tools: Agent, Read, Write, Edit, Bash, Grep, Glob
---

## Plugin paths (read first)

Reference/templates/scripts ship with this plugin under `${CLAUDE_PLUGIN_ROOT}/…`.
Create the project folder under the **current working directory**:
`estimating-projects/<project-slug>/`. Pass subagents the absolute project path AND the
`${CLAUDE_PLUGIN_ROOT}` location.

Drive the construction preconstruction pipeline for: **$ARGUMENTS**

**Market sector: public / government bid (Florida).** This command is the standard `/bid` pipeline (takeoff →
optional procurement → scope → estimate → proposal → audit) with the sector profile
applied. You are the precon coordinator — orchestrate the specialist subagents; do not do
their work yourself.

0. **Sector setup.** Read `${CLAUDE_PLUGIN_ROOT}/reference/sector-public-bidding.md` yourself, and pass its path to EVERY subagent
   you delegate to (takeoff-engineer, procurement-specialist, scope-writer, cost-estimator,
   bid-proposal-writer, estimate-auditor) with the instruction to apply its
   pipeline-stage changes, division emphasis, and markup/commercial posture.

0b. **Bid history check (Ideal repo only).** If the working directory contains Ideal's `bid_tracker/`
   package and `BID_TRACKER_DATA` points at its private data, run
   `python3 -m bid_tracker benchmark --project-type <code> --agency-type <type> --gsf <GSF>` and
   `python3 -m bid_tracker gonogo --project-type <code> --agency <agency_id> --cost <rough cost>` and report the
   segment n, escalated low $/SF band, median bidders, gap, and every flag (STOP ends the pursuit unless the
   owner overrides; n < 5 is directional). Otherwise state that no bid-history benchmark is available and continue.

1–7. **Follow the `/bid` pipeline steps** (project folder under `estimating-projects/<slug>/`,
   takeoff, optional live procurement, scope, estimate + workbook, proposal, independent
   audit, report back) — with these sector gates enforced on top:

- **Bond posture:** bid bond per the ITB (typ. 5%); P&P bond per FL 255.05 — set `bond_pct` > 0 in markups.csv unless the solicitation waives it. The validator flags `--sector public` with bond at 0.
- **Owner Direct Purchase (ODP):** have the procurement-specialist flag ODP candidates (big-ticket materials the owner buys tax-exempt); the estimator carves the sales tax accordingly.
- **Responsiveness gate:** every addendum acknowledged; the owner's bid form reproduced exactly; unit-price schedule as designed; no qualifications the ITB forbids. A responsive-but-wrong bid loses money; a non-responsive bid is thrown out — the proposal-writer checks both.
- **Certified payroll / Davis-Bacon:** if federal funds are in the project, price the wage determinations and the compliance admin.
- **No post-bid negotiation:** contingency and escalation must be IN the number on bid day.
- **Market position before OH&P:** once the cost-estimator has cost before OH&P (direct + GCs + bonds + insurance),
  run `python3 -m bid_tracker position --cost <C> --ee <EE> --project-type <code> --agency-type <type> --gsf <GSF>`
  (no published EE: `--expected-median <M>`; scored RFP: `--method best_value --competitor-price <P> --price-weight <W> --nonprice-gap <D>`).
  Hand the table to the cost-estimator and justify the OH&P against it. It never lowers bond, insurance or
  general-conditions floors; refused or thin-history output is directional only. (Ideal repo only.)

Validator: the cost-estimator and auditor must run
`python3 ${CLAUDE_PLUGIN_ROOT}/scripts/validate_estimate.py <project_dir>/ --sector public`
and clear every FAIL before the bid is declared ready.

8. **After bid opening:** harvest the tab with `/bid-tabs <tab URL>` and record Ideal's bid and result with
   `python3 -m bid_tracker pursuit update <sol_ref> --bid <amount> --result won|lost --rank <n>`. On every scored
   RFP, request the scorecards and the winners' cost sheets (Ch. 119) and log the debrief. (Ideal repo only.)
