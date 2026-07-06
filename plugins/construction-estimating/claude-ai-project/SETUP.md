# Set up the chat version in Claude.ai (5 minutes)

This folder mirrors the Claude Code plugin for use inside a **Claude.ai Project** — useful
for quick scopes, RFIs, and sanity checks from your phone or browser when you don't have
Claude Code in front of you. The full automation (subagents, `/bid`, Excel builders) still
lives in Claude Code; this is the chat-friendly subset.

## One-time setup

1. Sign in at **claude.ai** (a paid plan is required to create Projects).
2. **New Project** → name it e.g. *"Construction Estimating — FL"*.
3. **Custom instructions** → open `PROJECT_INSTRUCTIONS.md` in this folder and paste the
   entire body (everything after the first heading) into the Project's *Instructions* field.
4. **Project knowledge** → upload these seven files from the `knowledge/` folder:
   - `florida-code.md`
   - `csi-divisions.md`
   - `estimating-methodology.md`
   - `deliverable-templates.md`
   - `takeoff-accuracy-protocol.md`
   - `estimating-accuracy-protocol.md`
   - `sector-profiles.md`
5. Done. Start a new conversation **in this Project** for every job.

## Typical chat workflows

- **Quick takeoff** — drop in one or two plan sheets (PDF), say
  *"Take off the structural concrete on S1.0 per CSI Division 03, output the standard
  table with confidence flags and RFIs."*
- **Scope of work** — paste a takeoff or describe the project; ask
  *"Write the executive scope of work for a CGC bidding the whole house, walking the
  scope-gap checklist."*
- **Budgetary estimate (CSV)** — once you have quantities:
  *"Price this as a budgetary FL coastal residential bid. Output the line items in the
  CSV schema from `deliverable-templates.md` so I can paste it into the local workbook
  builder."*
- **Sanity check / audit** — paste a takeoff or estimate (yours or someone else's) and
  ask *"Audit this independently — math, scope gaps, FL code, reasonableness — rank
  findings by severity."*
- **Bid proposal text** — *"Write the cover letter and bid proposal from this scope
  + bid total."*

## What still happens locally (in Claude Code)

When you have an estimate CSV from chat, open **Claude Code** (with the
construction-estimating plugin installed) in your working folder, drop the CSV into
your project folder, and ask: *"build the estimate workbook for this project"* —
Claude runs the bundled builder and produces the formula-driven `estimate.xlsx`
plus `estimate-summary.md`. For the 13-tab bank loan package, run `/loan-package`
there instead (it walks the config + optional logo).

(Do NOT try to run `python3 plugins/...` paths by hand — those paths don't exist on
a marketplace install; the plugin's scripts live where Claude Code installed it.)

## Notes & honest limits

- The Project's knowledge gives the chat Florida-correct defaults; **for out-of-state
  jobs**, tell the chat the AHJ and code edition in your first message.
- Chat can't run code or build Excel files — it produces CSV/markdown for you to
  finish locally. The deterministic validator also only runs in Claude Code; in chat,
  the accuracy-protocol gates are performed manually and any chat takeoff/estimate is
  preliminary until re-run through the Code pipeline.
- Each conversation in a Project is independent — for a multi-step job, keep the same
  conversation open and feed all docs at the start.
- Don't paste confidential pricing into the Project Knowledge — keep the Knowledge as
  generic reference; per-job data stays in the conversation.
