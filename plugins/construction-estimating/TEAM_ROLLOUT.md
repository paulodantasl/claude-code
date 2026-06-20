# Team Rollout Guide — Construction Estimating Plugin

This is the 1-pager to send your team so they can use this on their own bids.

## TL;DR (3 lines)

```
/plugin marketplace add paulodantasl/claude-code
/plugin install construction-estimating@claude-code-plugins
pip install openpyxl
```

Then in any project folder: `/bid <project name>`, or just describe the task
("take off the structural concrete from these plans"). Done.

## Prerequisites

- **Claude Code** installed — web (claude.ai/code), desktop (Mac/Windows), CLI, or VS Code / JetBrains extension. Any one works.
- **Python 3** with **openpyxl** for the Excel builders — `pip install openpyxl` (or `pip3`).
- **Read access** to the `paulodantasl/claude-code` GitHub repo. If it's private, an invite is required. (If you want this hosted under an Ideal org repo for tighter control, fork there and adjust the marketplace install URL.)

## Pre-merge install (until PR #4 lands on `main`)

Until the plugin entry is merged to the default branch, install from the working branch:

```
/plugin marketplace add paulodantasl/claude-code@claude/eager-tesla-G40LH
/plugin install construction-estimating@claude-code-plugins
```

After PR #4 merges, the cleaner form `paulodantasl/claude-code` (no `@branch`) will work.

## What you get

- 6 specialist agents (`takeoff-engineer`, `scope-writer`, `cost-estimator`, `bid-proposal-writer`, `estimate-auditor`, `procurement-specialist`) — Claude auto-routes based on your task
- `/bid <project>` — full precon pipeline (takeoff → scope → estimate → proposal → audit)
- Florida code + CSI + estimating-methodology knowledge base
- Two Excel builders: line-item **estimate workbook** (Detail + Summary, formula-driven) and 13-tab **bank construction-loan package** (Cover, Sources & Uses, AIA G703 Schedule of Values, Draw Schedule, Gantt, etc.)

## First-day usage

1. **Open Claude Code in your working folder** (anywhere — not in this repo).
2. **Drop your plans** (PDF) into a project folder of your choice. The agents recommend `estimating-projects/<your-slug>/plans/`.
3. **Optional: drop `logo.png`** into the project folder if you want the loan package branded.
4. **Optional: copy the loan-package config template** to your project folder when you're ready to build the bank workbook — Claude will fetch it from the plugin or you can copy it yourself.
5. **Talk to Claude** — *"take off the foundation from S1.0", "write a scope for this house as a Florida CGC", "price the takeoff with budgetary FL coastal costs and build the workbook"*. Or run `/bid <project name>` to do the whole pipeline.

## Where your work goes (and what NEVER to commit)

- All deliverables (`takeoff.md`, `scope-of-work.md`, `lineitems.csv`, `estimate.xlsx`, `construction-loan-package.xlsx`, etc.) write to your **current working directory** under `estimating-projects/<slug>/`.
- They do **NOT** live inside the plugin (which gets replaced on `/plugin marketplace update`).
- **NEVER** commit `estimating-projects/` to any shared repo — it contains owner names, lender info, real pricing, and sealed drawings. Add it to your repo's `.gitignore` if you keep one. Each person's bid data should stay on their machine.

## Updates

When this plugin changes (new code rules, fixed bugs, FL code edition rolls):

```
/plugin marketplace update claude-code-plugins
```

Plugin files are replaced — your project folders aren't touched.

## Troubleshooting

| Symptom | Fix |
|---|---|
| `/bid` not recognized | Restart Claude Code session after install so it indexes the plugin |
| Agents can't find reference docs | They use `${CLAUDE_PLUGIN_ROOT}`; if it fails, the agents have a Glob/find fallback — just re-run |
| `openpyxl` not found when building Excel | `pip install openpyxl` (use `pip3` on macOS if `pip` points at Python 2) |
| Workbook builds but no logo | Drop `logo.png` in the project folder, or set `company.logo: "<path>"` in `loan-package-config.json` |
| Numbers look soft | They're budgetary — the auditor agent will flag this. Replace `unit_*` costs in `lineitems.csv` with real sub quotes and re-run the Excel builder |
| Out-of-state job | Tell the agent the AHJ and code edition up front; the methodology and CSI still apply, only the FL specifics change |

## Chat-only fallback (Claude.ai, no Code)

If a coworker is on the phone or doesn't have Claude Code handy, see
`plugins/construction-estimating/claude-ai-project/SETUP.md` — a 5-minute Claude.ai
Project setup that mirrors the knowledge base + a consolidated system prompt. Good for
quick scopes and RFIs; the full Excel automation still lives in Claude Code.

## Who to ask

- Plugin issues / feature requests → open an issue against the repo (`paulodantasl/claude-code`) or message the maintainer.
- Bid-strategy / pricing questions → these are the user's call; the auditor agent surfaces risk and reasonableness, the human decides the number.
