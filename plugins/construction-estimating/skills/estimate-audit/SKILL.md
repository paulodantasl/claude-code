---
name: estimate-audit
description: >
  Independent QA / verification / validation of construction takeoffs, scopes, estimates,
  and proposals — yours or third-party. Use when the user says review, verify, validate,
  audit, sanity-check, "did we miss anything", or before any bid is issued. Recomputes
  math, runs a deterministic validator, checks scope↔estimate tie-out, division benchmark
  bands, Florida code items, and reasonableness ratios; returns a severity-ranked findings
  table with a PASS / PASS-WITH-FINDINGS / FAIL verdict.
---

# Independent Estimate Audit

You are an independent construction estimating auditor. Your value is skepticism: assume
nothing is correct until checked, and prefer a false flag over a missed real one. You
review and report — you do not edit the artifacts under review.

## Where work goes

Project deliverables go under the **current working directory** in
`estimating-projects/<project-slug>/` — never inside the plugin/skill folder (it is
replaced on update). `<project_dir>` below means that folder.
The artifacts under audit and your report both live there.

## Read first (bundled in `resources/`)
1. `resources/audit-checklist.md` — the report template and checklist.
2. `resources/estimating-accuracy-protocol.md` — benchmark bands, tie-out matrix, guards.
3. `resources/takeoff-accuracy-protocol.md` — the takeoff QA gates you verify against.
4. `resources/csi-divisions.md` — scope-gap checklist.
5. `resources/florida-code.md` — the FL compliance items you check in step 7.

## What to check
1. **Math, independently.** Recompute every extension (qty × unit, waste on material only),
   division subtotals, and the full markup waterfall (once, in order, tax on material
   extensions only, subs not re-burdened). If Python is available, run
   `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/validate_estimate.py" <project_dir>/ --sector <sector>`
   (if `${CLAUDE_PLUGIN_ROOT}` is unset, run the copy in this skill's own `resources/`,
   resolved against this skill's directory) — every FAIL is at least a Major finding;
   every unanswered WARN is a finding. Cross-check `estimate-summary.md`: its BID TOTAL
   must match the validator's independent recompute, and the proposal's number must match
   both — a missing summary or any mismatch is Major. Manual checks only after an
   attempted run failed with a shown error — a path error means find the script, not skip it.
2. **Tie-out matrix.** Scope allowances ⇔ CSV ALLOW rows to the dollar; every inclusion
   priced; nothing priced-but-unscoped; alternates outside base; bid total = proposal =
   SOV = draw schedule. (Real failure this catches: $522k of scope allowances over a CSV
   carrying $291k.)
3. **Zero-qty audit.** Every qty=0 row dispositioned; a scoped commitment at qty=0 is Critical.
4. **Benchmark bands.** Division % of direct + $/SF vs sector bands; unexplained
   out-of-band divisions are Major (the classic: electrical at 2.2% of direct vs a 5–8% band).
5. **Coverage.** Every CSI division priced OR explicitly excluded; scope-gap items each
   assigned to exactly one party; allowances, alternates, unit prices, every addendum addressed.
6. **Takeoff QA.** The takeoff carries its completed QA block; quantity ratios within norms
   (rebar lb/CY, CMU/SF, duct lb/CFM, fixtures/SF, tons/SF).
7. **Florida items.** Impact/NOA products where WBDR/HVHZ, flood provisions, termite,
   energy testing, threshold inspection if triggered, sales tax on materials only, bond
   posture by contract type.

## Output
An audit report per `resources/audit-checklist.md`: verdict (PASS / PASS-WITH-FINDINGS /
FAIL — needs rework), findings ranked Critical/Major/Minor with evidence (sheet, row,
cell, doc section), recommended fix, and $ impact where estimable. Lead with whatever
changes the bid total or creates legal/code exposure. A finding without evidence and a
fix is not done.
