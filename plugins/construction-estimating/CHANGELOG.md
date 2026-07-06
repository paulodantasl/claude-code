# Changelog — construction-estimating plugin

## 1.1.0 (2026-07)
- `build_estimate_xlsx.py` now also writes `estimate-summary.md` (plain-text BID TOTAL +
  waterfall) — the canonical handoff for the proposal writer and auditor; workbook markup
  formulas now reference the editable rate cells (what-if edits recompute).
- New `/loan-package` command; loan builder bundled into the residential skill; logo now
  optional everywhere (pillow/pymupdf install documented, graceful degradation added).
- Accuracy protocols: quantity-ratio band table embedded in the takeoff protocol §8;
  takeoff template carries the QA block; audit checklist gains release-blocker gates;
  as-of dates on all reference docs (FBC 9th-Edition succession noted).
- Agents pin `model: sonnet`; takeoff subagent gets an explicit no-MCP fallback branch;
  run logs write to the project folder, never inside the plugin.
- Sector gates reconciled across commands/skills (FL 558 warranty, retainage/prompt-pay,
  public `bond_pct` wiring); skills invoke scripts via `${CLAUDE_PLUGIN_ROOT}` with a
  resources/ fallback.

## 1.0.0
- Initial release: 6 agents, 5 bid commands, 8 skills, validator + two Excel builders,
  Florida knowledge base, Claude.ai chat package.
