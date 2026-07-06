# Changelog — construction-estimating plugin

## 1.1.0 (2026-07)

Deterministic handoffs and gate hardening, from a 360 review of the toolkit.

- **`estimate-summary.md`** — `build_estimate_xlsx.py` now writes a plain-text BID TOTAL,
  per-division costs, and the full markup waterfall alongside `estimate.xlsx`. It is the
  canonical number for the proposal and the audit: the proposal writer (which has no Bash
  and cannot evaluate a formula-only workbook) reads it instead of hand-recomputing, and
  the auditor cross-checks it against the validator's independent recompute. The `/bid`
  done-gate now requires it.
- **Proposal tie-out protocol** — a terminal, mandatory checklist in `bid-proposal-writer`
  (figures taken verbatim from `estimate-summary.md`, alternates/allowances checked to the
  dollar against source, inclusions diffed against the scope, every addendum acknowledged).
- **Gates made mechanical** — quantity-ratio band table embedded in the takeoff protocol §8
  (it previously pointed at numbers that existed nowhere); the takeoff template now carries
  the mandatory QA block and the confidence taxonomy; the audit checklist gains
  release-blocker gates including the `estimate-summary` tie and price-validity window.
- **Reference staleness** — `as-of: 2026-07` headers on every reference doc, a stated
  rounding convention, and an honest note that the validator's allowance scan is
  best-effort (the to-the-dollar tie-out remains a manual matrix check).
- **Robustness** — Pillow and PyMuPDF are now optional at runtime with actionable messages
  instead of tracebacks (both declared in `requirements.txt`); the validator fails cleanly
  on an empty or headerless CSV; the workbook builder reports a missing `lineitems.csv`
  with a pointer to the schema.
- **Skills** — script invocations resolve through `${CLAUDE_PLUGIN_ROOT}` with a
  `resources/` fallback and no silent skip-to-manual; negative triggers added to the four
  sector skills so they stop poaching each other's jobs; `florida-code.md` added to the
  audit skill's read-first list; the loan-package builder and config template bundled into
  the residential skill so it works standalone in Cowork.
- **Subagent/MCP** — agents carry explicit `model:` pins (sonnet across the plugin so every
  seat can run them), and the takeoff subagent now has an explicit branch for when the
  Pave MCP connector is absent from its tool list instead of improvising API calls.
- **Sector gates reconciled** across commands, skills, and profiles: FL Ch. 558 warranty
  posture (residential), retainage / prompt-payment caps (public), and `bond_pct > 0`
  wiring (public).
- Chat package: both accuracy protocols and a condensed `sector-profiles.md` added to
  Project knowledge; instructions state that the validator runs only in Code and that chat
  output is preliminary until re-run there; procurement template added (5 → 6).

## 1.0.0
- Initial release: 6 agents, bid commands, 8 skills, validator + two Excel builders,
  Florida knowledge base, Claude.ai chat package.
