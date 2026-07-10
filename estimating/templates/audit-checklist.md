# Audit / Verification / Validation Report — {{PROJECT_NAME}}

| Field | Value |
|-------|-------|
| Work reviewed | {{takeoff / scope / estimate / proposal / external 3rd-party}} |
| Source files | {{paths or doc names}} |
| Reviewed by | estimate-auditor |
| Date | {{DATE}} |
| Verdict | **PASS / PASS-WITH-FINDINGS / FAIL — needs rework** |

## Findings (ranked)

> Severity: **Critical** (changes the number/loses money or non-compliant) ·
> **Major** (likely error or scope gap) · **Minor** (clarity/consistency).

| # | Severity | Area (Div / doc) | Finding | Evidence | Recommended fix |
|---|----------|------------------|---------|----------|-----------------|
| 1 | Critical | Div 08 | Impact-rated glazing not carried; project is in WBDR | A-601 notes large-missile impact; estimate line is generic glazing | Re-price to NOA/FL# impact units; +$____ |
| 2 | | | | | |

## Checks performed

**Mechanical / protocol gates (run these, don't eyeball them)**
- [ ] `validate_estimate.py --sector <sector>` run on the workbook inputs — PASS (attach output)
- [ ] Scope ↔ estimate tie-out matrix verified line-by-line
- [ ] Zero-qty / zero-cost line audit (no silent placeholders)
- [ ] Benchmark bands checked against the sector profile table
- [ ] Takeoff QA block present and complete (or its failures explained)
- [ ] Sector red-flag list walked (from the matching sector-*.md profile)

**Math & structure**
- [ ] All extensions (qty × unit) recomputed and tie out
- [ ] Division subtotals and grand total foot
- [ ] Rounding consistent; no transposition/units errors

**Coverage**
- [ ] Every CSI division priced OR explicitly excluded (no silent gaps)
- [ ] Scope-gap items each assigned to exactly one party (no double-count / hole)
- [ ] Allowances, alternates, unit prices, **all addenda** addressed

**Reasonableness**
- [ ] $/SF and trade-% bands plausible for building type & FL market
- [ ] Quantity ratios within norms (rebar/CY, CMU/SF, duct lbs/CFM, fixtures/SF)
- [ ] Unit costs within sane ranges; outliers explained

**Florida compliance**
- [ ] Wind/impact products (NOA/FL#) carried where required (HVHZ/WBDR)
- [ ] Flood provisions (zone/DFE/vents/breakaway) addressed
- [ ] Termite soil treatment, FBC-Energy testing carried
- [ ] Threshold inspection budgeted if applicable
- [ ] Material sales tax (6% + surtax) applied to materials only
- [ ] Bonds/insurance/permit handled correctly

**Markups**
- [ ] GCs reasonable vs. schedule/staffing (not just a %)
- [ ] Markups applied once, in order; subs not re-burdened
- [ ] Contingency/escalation appropriate

**Consistency across deliverables**
- [ ] Scope inclusions/exclusions match the estimate line items
- [ ] Proposal price = estimate bid total; alternates/allowances agree

## Summary
2–4 sentences: overall quality, biggest risks, and whether it is ready to issue.
