---
description: Independent QA audit of a takeoff, scope, estimate, or proposal — ours or a third party's.
argument-hint: <project name, path to the project folder, or the third-party file to audit>
allowed-tools: Agent, Read, Write, Bash, Grep, Glob
---

Run an independent audit of: **$ARGUMENTS**

Delegate to the `estimate-auditor` subagent — it carries the audit checklist, both accuracy
protocols, and the deterministic validator, and knows where its knowledge base lives.

1. **Identify what is being audited.** Either this pipeline's own deliverables in a project
   folder, or a third-party/prior estimate the user wants validated. For third-party work,
   ask for whatever basis exists (plans, scope, the estimate file) and be explicit about
   what could not be verified for lack of a basis.
2. **Pass the sector if known** (public / residential / commercial / tenant-improvement) so
   the agent checks against the matching benchmark bands.
3. **Delegate.** The agent must:
   - recompute the math independently rather than trusting the workbook's own totals;
   - run the bundled `validate_estimate.py` with the matching `--sector` flag;
   - hunt scope gaps and double-counts between trades;
   - check Florida compliance (HVHZ/impact, flood, termite, energy, threshold, sales tax,
     bonds);
   - test reasonableness against benchmarks ($/SF, division shares, labor/material ratios).
4. **Write `audit-report.md`** with findings graded Critical / Major / Minor.

When it returns, lead with the verdict and every Critical and Major finding — do not bury
them under what passed. Offer to loop the responsible agent to fix them and then re-audit.

Run this before any bid is issued, even when the earlier stages looked clean. The auditor
surfaces risk; the number itself is always the user's call.
