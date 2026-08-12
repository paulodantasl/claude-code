---
description: Live material sourcing — real suppliers, current pricing, availability, and lead times, every price cited.
argument-hint: <project name, path to the project folder, or the material list to source>
allowed-tools: Agent, WebSearch, WebFetch, Read, Write, Edit, Bash, Grep, Glob
---

Source materials for: **$ARGUMENTS**

Delegate to the `procurement-specialist` subagent — it carries the procurement template and
the Florida product-approval reference, and knows where its knowledge base lives.

1. **Locate the material list.** `lineitems.csv` or `takeoff.md` in the project folder, or
   whatever list the user supplied. If the list is long, agree on scope first — this stage
   is time-intensive because every price is looked up live.
2. **Confirm the delivery location** (city/county) — it drives distributor coverage, freight,
   and Florida product-approval applicability (NOA / FL#).
3. **Delegate.** For each material the agent searches the web in real time for actual
   suppliers, current price, availability, and **lead time**, and produces `procurement.md`
   plus `procurement.csv`.
4. **Enforce the citation rule.** Every price carries a source URL and an access date. A
   price that cannot be sourced is reported as *not found* — never filled in from memory,
   never estimated into the table. Hold the agent to this; a fabricated price here poisons
   the estimate downstream.

When it returns, report: what was sourced versus not found, the long-lead items that could
drive the schedule, and any Florida product-approval gaps (materials without a valid NOA or
FL# for the jurisdiction).

Feed the result into `/estimate` — the cost-estimator uses these sourced prices in place of
budgetary plugs. Prices and lead times move; treat them as valid as of the access date.
