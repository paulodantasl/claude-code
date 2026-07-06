---
description: Fan canonical estimating/ files out to every plugin copy (or check for drift).
argument-hint: "[--check]"
allowed-tools: Bash(python3 estimating/scripts/sync_plugin.py:*), Read, Grep, Glob
---

Run the canonical→copies sync for the construction-estimating plugin: **$ARGUMENTS**

- `--check` (default before any commit): `python3 estimating/scripts/sync_plugin.py --check`
  — reports drift and exits nonzero if any plugin copy differs from its canonical file.
- `--write` (after editing anything under `estimating/reference|templates|scripts`):
  `python3 estimating/scripts/sync_plugin.py --write` — copies canonical over the copies.

Rules: NEVER hand-edit a plugin copy (edit the canonical file and sync). If --check
reports drift you didn't cause, the copy was hand-edited — diff it, port anything
valuable INTO the canonical file, then --write. After a real content change, bump the
version in `plugins/construction-estimating/.claude-plugin/plugin.json` (mirror it in
`.claude-plugin/marketplace.json`) and add a line to the plugin's `CHANGELOG.md`.
Remind the user: the Claude.ai Project knowledge does not sync from git — changed
knowledge files must be re-uploaded there manually.
