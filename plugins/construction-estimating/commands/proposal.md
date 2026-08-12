---
description: Client/GC-facing bid proposal and cover letter — base bid, alternates, allowances, unit prices, FL qualifications.
argument-hint: <project name or path to the project folder>
allowed-tools: Agent, Read, Write, Edit, Grep, Glob
---

Write the bid proposal for: **$ARGUMENTS**

Delegate to the `bid-proposal-writer` subagent — it carries the proposal template and the
Florida qualification language, and knows where its knowledge base lives.

1. **Gather the basis.** `estimate.xlsx` / `lineitems.csv` / `markups.csv` for the numbers
   and `scope-of-work.md` for the narrative. Both must exist — a proposal written without a
   priced, scoped basis is a guess. Run `/estimate` and `/scope` first if either is missing.
2. **Confirm the addressee and posture** — who is receiving it (owner, GC, agency), the due
   date and format required, and whether alternates or unit prices were requested.
3. **Delegate.** The agent produces `bid-proposal.md`: base bid price, alternates,
   allowances, unit prices, schedule, and the Florida qualifications block (license number,
   bond and insurance posture, lien-law notice).
4. **Tie out the numbers.** Every figure in the proposal must match the estimate and the
   scope. If anything disagrees, stop and reconcile before delivering — a proposal that
   contradicts its own estimate is the single most expensive error in this pipeline.

When it returns, report: the base bid, each alternate and its adder/deduct, the allowances
carried, and anything in the proposal that is still a placeholder.

This is the proposal stage only. Run `/audit` before issuing, and `/bid` for the full
pipeline.
