---
description: Executive scope of work only — inclusions, exclusions, clarifications, allowances, alternates, VE.
argument-hint: <project name, or path to the project folder / bid documents>
allowed-tools: Agent, Read, Write, Edit, Grep, Glob
---

Write the executive scope of work for: **$ARGUMENTS**

Delegate to the `scope-writer` subagent — it carries the CSI division map, the scope-gap
checklist, and the Florida code reference, and knows where its knowledge base lives.

1. **Gather the basis.** The takeoff (`takeoff.md`) if one exists, plus bid documents,
   drawings, and specs. If there is no takeoff yet, say so — the scope can still be written
   from the documents, but flag that it has not been reconciled against measured quantities.
2. **Confirm the bidding posture** — GC (whole-building) or specialty subcontractor, and
   which divisions are being carried. This changes every exclusion. Ask if unstated.
3. **Pass the sector if known** (public / residential / commercial / tenant-improvement) so
   the agent applies the matching profile.
4. **Delegate.** The agent produces `scope-of-work.md` in the project folder, organized by
   CSI division: inclusions, exclusions, clarifications, assumptions, allowances (each with
   a cap and a reconciliation rule), alternates, and value-engineering options.

When it returns, report: the divisions carried, the exclusions most likely to be contested,
every allowance and its cap, and any gap between the scope and the takeoff. Exclusions are
where bids are won and lost — surface the aggressive ones rather than burying them.

This is the scope stage only. Quantities are `/takeoff`, pricing is `/estimate`, and the
full pipeline is `/bid`.
