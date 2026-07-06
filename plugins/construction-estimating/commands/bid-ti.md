---
description: Run the preconstruction pipeline for a commercial buildout / tenant improvement (Florida) — sector-tuned gates over the standard /bid flow.
argument-hint: <project name, or path to a folder of plans/specs>
allowed-tools: Task, Agent, Read, Write, Edit, Grep, Glob, Bash(python3 ${CLAUDE_PLUGIN_ROOT}/scripts/*), Bash(mkdir:*)
---

## Plugin paths (read first)

Reference/templates/scripts ship with this plugin under `${CLAUDE_PLUGIN_ROOT}/…`.
Create the project folder under the **current working directory**:
`estimating-projects/<project-slug>/`. Pass subagents the absolute project path AND the
`${CLAUDE_PLUGIN_ROOT}` location.

Drive the construction preconstruction pipeline for: **$ARGUMENTS**

**Market sector: commercial buildout / tenant improvement (Florida).** This command is the standard `/bid` pipeline (takeoff →
optional procurement → scope → estimate → proposal → audit) with the sector profile
applied. You are the precon coordinator — orchestrate the specialist subagents; do not do
their work yourself.

0. **Sector setup.** Read `${CLAUDE_PLUGIN_ROOT}/reference/sector-tenant-improvement.md` yourself, and pass its path to EVERY subagent
   you delegate to (takeoff-engineer, procurement-specialist, scope-writer, cost-estimator,
   bid-proposal-writer, estimate-auditor) with the instruction to apply its
   pipeline-stage changes, division emphasis, and markup/commercial posture.

1–7. **Follow the `/bid` pipeline steps** (project folder under `estimating-projects/<slug>/`,
   takeoff, optional live procurement, scope, estimate + workbook, proposal, independent
   audit, report back) — with these sector gates enforced on top:

- **Existing conditions first:** require (or price) the field-verification walk — above-ceiling survey, panel capacity, RTU age/tonnage, structural check before new loads. As-builts lie; the contingency (10–15%) reflects that.
- **Asbestos survey:** confirm the pre-renovation asbestos survey status before pricing demo (required for commercial renovation/demolition).
- **Landlord ecosystem:** work letter read and reconciled (TI allowance, landlord fees, building standards); landlord-mandated vendors identified BEFORE procurement — those lines are QUOTE-REQ to the mandated vendor, not competitively bid.
- **Logistics premiums priced:** after-hours work, freight elevator windows, protection, negative air, fire-watch/impairment permits for sprinkler/FA tie-ins.
- **Code triggers checked:** FBC-Existing Building alteration level, change-of-occupancy, ADA path-of-travel obligation on alterations.

Validator: the cost-estimator and auditor must run
`python3 ${CLAUDE_PLUGIN_ROOT}/scripts/validate_estimate.py <project_dir>/ --sector ti`
and clear every FAIL before the bid is declared ready.
