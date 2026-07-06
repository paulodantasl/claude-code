# CLAUDE.md

## What this repo is

Ideal Construction's own tooling, layered on a fork of anthropics/claude-code.

- **Ours (edit freely):** the preconstruction system — `estimating/`,
  `plugins/construction-estimating/`, `.claude/{agents,commands,skills}` — plus the
  standalone tools at the repo root (`permit_scraper/`, `flight_monitor/`,
  `ideal_apis/`, `planhub_gc_scraper.py`).
- **Upstream (don't modify outside a deliberate sync):** everything inherited from
  anthropics/claude-code — the other `plugins/*`, `examples/`, `scripts/`, `.github/`,
  `CHANGELOG.md`, `demo.gif`.

When a new top-level directory appears and you can't place it, check `git log` for who
added it rather than assuming it is upstream.
Maps: `estimating/README.md` (system) · `plugins/construction-estimating/TEAM_ROLLOUT.md`
(team install, Cowork, chat).

## Where work goes (hard rule)

- Project deliverables: `estimating/projects/<slug>/` (lowercase-hyphenated slug, reused
  by every pipeline stage). Layout: `estimating/projects/README.md`.
- `estimating-projects/` is the PLUGIN-install convention only — never create it here.
- Never commit client data: `estimating/projects/*` is gitignored except its README.

## Bid pipeline contract

- Commands: `/bid` (+ `/bid-residential`, `/bid-commercial`, `/bid-public`, `/bid-ti`)
  runs the whole pipeline; the per-stage commands `/takeoff`, `/scope`, `/estimate`,
  `/proposal`, `/audit`, `/procure`, `/loan-package` run one stage each. `/sync` is the
  drift gate.
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
- Toolkit scripts live one level up: `estimating/sync.py` (drift gate),
  `estimating/install.py` (machine-wide `~/.claude` install), and
  `estimating/package_skills.py` (validating zips for Cowork / claude.ai upload).

## Source of truth & sync

- `estimating/{reference,templates,scripts}` are CANONICAL. Their mirrors — the plugin
  bundle, every Agent Skill's `resources/`, and the repo-level `.claude/skills/` copies —
  are generated; never hand-edit a mirror. Agents and the `/bid*` commands are authored
  per surface (plugin copies carry `${CLAUDE_PLUGIN_ROOT}` paths) and are NOT synced: a
  content change to one must be mirrored into its twin by hand.
- `estimating/sync.py` owns this. After canonical edits: `/sync --write`; before
  committing: `/sync --check`. Then bump the plugin version + CHANGELOG for the next
  team release. Do not add a second sync mechanism — one gate, or it stops being a gate.
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

- The upstream automation that posted to Anthropic's tracker is removed (the `/dedupe`
  and `/triage-issue` commands and the four issue-bot workflows that hardcoded
  `anthropics/claude-code`). Never post to that tracker from this fork; treat any
  remaining upstream workflow as inert unless you've read what repo it targets.
- On upstream merges: keep OURS for `.claude-plugin/marketplace.json`, `README.md`,
  `.gitignore`, `requirements.txt`; then run `/sync --check`.
