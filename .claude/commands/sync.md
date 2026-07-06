---
description: Fan the canonical estimating/ files out to every mirrored copy (or check for drift).
argument-hint: "[--check|--write]"
allowed-tools: Bash(python3 estimating/sync.py:*), Read, Grep, Glob
---

Run the canonical→copies sync for the estimating toolkit: **$ARGUMENTS**

- `--check` (run before any commit): `python3 estimating/sync.py --check` — drift gate;
  exits nonzero if any mirrored copy differs from its canonical file.
- `--write` (after editing anything under `estimating/reference|templates|scripts`):
  `python3 estimating/sync.py --write` — regenerates every derived copy.

Canonical is `estimating/{reference,templates,scripts}`. Mirrors are the plugin bundle,
each Agent Skill's `resources/`, and the repo-level `.claude/skills/` copies.

Rules: NEVER hand-edit a mirrored copy — edit the canonical file and sync. If `--check`
reports drift you didn't cause, a copy was hand-edited: diff it, port anything valuable
INTO the canonical file, then `--write`. Agents and the `/bid*` commands are authored
per surface and deliberately NOT synced — a content change to one must be mirrored into
its twin by hand.

After a real content change, bump `plugins/construction-estimating/.claude-plugin/plugin.json`
(mirror it in `.claude-plugin/marketplace.json`) and add a line to the plugin's
`CHANGELOG.md`. Then remind the user: the Claude.ai Project knowledge does not sync from
git — changed files under `claude-ai-project/knowledge/` must be re-uploaded there by hand.
