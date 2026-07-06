# CLAUDE.md

## What this repo is

Ideal Construction's Florida preconstruction system, layered on a fork of
anthropics/claude-code. The work product is `estimating/` +
`plugins/construction-estimating/` + `.claude/{agents,commands}`; everything else is
upstream — don't modify upstream files except during deliberate upstream syncs.
Maps: `estimating/README.md` (system) · `plugins/construction-estimating/TEAM_ROLLOUT.md`
(team install, Cowork, chat).

## Where work goes (hard rule)

- Project deliverables: `estimating/projects/<slug>/` (lowercase-hyphenated slug, reused
  by every pipeline stage). Layout: `estimating/projects/README.md`.
- `estimating-projects/` is the PLUGIN-install convention only — never create it here.
- Never commit client data: `estimating/projects/*` is gitignored except its README.

## Bid pipeline contract

- Commands: `/bid` (+ `/bid-residential`, `/bid-commercial`, `/bid-public`, `/bid-ti`),
  `/loan-package`, `/sync-plugin`.
- Agent order: takeoff-engineer → (procurement-specialist) → scope-writer →
  cost-estimator → bid-proposal-writer → estimate-auditor (mandatory; on Critical/Major
  findings: fix → re-audit).
- Done gate: a bid is NOT ready until takeoff.md, scope-of-work.md, lineitems.csv,
  markups.csv, estimate.xlsx, estimate-summary.md, bid-proposal.md, audit-report.md all
  exist AND `python3 estimating/scripts/validate_estimate.py estimating/projects/<slug>/
  --sector <residential|commercial|ti|public>` reports 0 FAIL.
- The BID TOTAL comes from `estimate-summary.md` only — never recompute it by hand or
  quote it from memory.

## Non-negotiables for estimating work

- Never invent quantities or prices. Label every line's basis
  (sourced/quote/budgetary/allowance/plug); plugs expire. Conflicts become RFIs, never
  silent picks. The accuracy protocols in `estimating/reference/` are hard gates.
- `lineitems.csv` header (exact, 12 columns): `division,section,item,description,qty,
  unit,unit_mat,unit_lab,unit_equip,unit_sub,waste_pct,notes`.

## Scripts & environment

- Always `python3`, never `python`. Deps: `pip install -r requirements.txt`
  (openpyxl, pillow, pymupdf for the estimating suite).
- The scripts in `estimating/scripts/` are deterministic gates: if one errors, fix the
  invocation or environment — never hand-compute the deliverable it produces.

## Source of truth & sync

- `estimating/{reference,templates,scripts}` are CANONICAL. Same-named files under
  `plugins/construction-estimating/` (reference/, templates/, scripts/,
  skills/*/resources/, claude-ai-project/knowledge/) are generated copies — never
  hand-edit a copy. Plugin `agents/` and `commands/` are intentionally path-adapted
  (`${CLAUDE_PLUGIN_ROOT}`, `estimating-projects/`) and NOT synced — content changes to
  a repo agent/command must be mirrored into its plugin twin by hand.
- After canonical edits: `/sync-plugin --write`; before committing: `/sync-plugin
  --check`. Then bump the plugin version + CHANGELOG for the next team release.
- Claude.ai Project knowledge never syncs from git — re-upload changed knowledge files
  (see `claude-ai-project/SETUP.md`) after each release.

## Models

- Repo agents pin: opus for takeoff-engineer + estimate-auditor (highest-judgment
  stages), sonnet elsewhere. Plugin agents pin sonnet everywhere (team seats may lack
  Opus). Sonnet-class models must be able to follow every prompt mechanically — keep
  gates explicit and checklists terminal when editing prompts.

## JobTread / Pave

- Connector = MCP tool `mcp__Ideal__query` (server "Ideal"). If a subagent lacks MCP
  access, run JobTread mode in the main thread via the `construction-takeoff` skill.
- Per-run logs go to `estimating/projects/<slug>/jobtread-runlog.md`; durable lessons
  also go to `estimating/reference/jobtread-takeoff-protocol.md` (repo checkout only).

## Fork hygiene

- Upstream issue automation is removed (dedupe/triage commands, the issue-bot
  workflows) — never post to anthropics/claude-code's tracker from this fork.
- On upstream merges: keep OURS for `.claude-plugin/marketplace.json`, `README.md`,
  `.gitignore`, `requirements.txt`; then run `/sync-plugin --check`.
