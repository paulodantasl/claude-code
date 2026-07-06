---
description: Run the preconstruction pipeline for a new commercial construction (Florida) — sector-tuned gates over the standard /bid flow.
argument-hint: <project name, or path to a folder of plans/specs>
allowed-tools: Task, Agent, Read, Write, Edit, Grep, Glob, Bash(python3 ${CLAUDE_PLUGIN_ROOT}/scripts/*), Bash(mkdir:*)
---

## Plugin paths (read first)

Reference/templates/scripts ship with this plugin under `${CLAUDE_PLUGIN_ROOT}/…`.
Create the project folder under the **current working directory**:
`estimating-projects/<project-slug>/`. Pass subagents the absolute project path AND the
`${CLAUDE_PLUGIN_ROOT}` location.

Drive the construction preconstruction pipeline for: **$ARGUMENTS**

**Market sector: new commercial construction (Florida).** This command is the standard `/bid` pipeline (takeoff →
optional procurement → scope → estimate → proposal → audit) with the sector profile
applied. You are the precon coordinator — orchestrate the specialist subagents; do not do
their work yourself.

0. **Sector setup.** Read `${CLAUDE_PLUGIN_ROOT}/reference/sector-commercial-new.md` yourself, and pass its path to EVERY subagent
   you delegate to (takeoff-engineer, procurement-specialist, scope-writer, cost-estimator,
   bid-proposal-writer, estimate-auditor) with the instruction to apply its
   pipeline-stage changes, division emphasis, and markup/commercial posture.

1–7. **Follow the `/bid` pipeline steps** (project folder under `estimating-projects/<slug>/`,
   takeoff, optional live procurement, scope, estimate + workbook, proposal, independent
   audit, report back) — with these sector gates enforced on top:

- **Delegated designs priced:** trusses, precast, curtain wall, fire suppression, fire alarm each carry their design-build engineering cost, not just material+labor.
- **Threshold + special inspections:** check the FL 553.79 trigger and the FBC Ch 17 special-inspections program; both are budget lines, not surprises.
- **Site/civil weight:** SWPPP/NPDES, FDOT/utility permits, impact & mobility fees — confirm who pays and carry accordingly.
- **Div 21/28 always evaluated:** sprinklers and fire alarm are in scope until explicitly excluded, and both AHJ reviews (building + fire marshal) are on the schedule.
- **Shell definition locked:** core & shell vs warm shell vs turnkey stated in the scope with the exclusion list to match.

Validator: the cost-estimator and auditor must run
`python3 ${CLAUDE_PLUGIN_ROOT}/scripts/validate_estimate.py <project_dir>/ --sector commercial`
and clear every FAIL before the bid is declared ready.
