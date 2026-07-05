# Construction Estimating — Deliverable Templates

Copies of the 5 template skeletons the GPT-side specialists fill in.
Use these formats for your takeoff / scope / estimate workbook / proposal / audit outputs.

---

## takeoff-template

# Quantity Takeoff — {{PROJECT_NAME}}

| Field | Value |
|-------|-------|
| Project | {{PROJECT_NAME}} |
| Location / AHJ | {{CITY, COUNTY, FL}} |
| Plan set | {{SET NAME}}, dated {{DATE}}, rev {{REV}} |
| Addenda incorporated | {{ADD #1 … }} |
| Takeoff by | {{AGENT}} |
| Date | {{DATE}} |
| Basis | PDF plans + specs / digitized import / mixed |
| Wind / Flood | V_ult {{___}} mph, Risk Cat {{___}}; Flood zone {{___}}, DFE {{___}} |

## Quantities by CSI division

> One row per measurable/countable item. State the **source** (sheet # or imported
> file), the **method** (measured / counted / calculated / imported), and a
> **confidence** flag. Mark anything scaled off a raster PDF as **approximate** and
> recommend verified measurement.

| Div | Item | Qty | Unit | Source (sheet) | Method | Confidence | Notes |
|-----|------|----:|------|----------------|--------|------------|-------|
| 03 | Slab-on-grade, 5" | | SF | S-201 | measured | approx | flag for verified TO |
| … | | | | | | | |

## Assumptions

- {{e.g., No geotech provided — assumed spread footings, no dewatering.}}

## Exclusions from this takeoff

- {{Items not quantified and why.}}

## RFIs / clarifications needed

- {{Conflicts between drawings and specs; missing details; illegible scales.}}

## Quantity reasonableness checks

- {{e.g., rebar 110 lbs/CY — within norm; CMU 1.125 units/SF — OK.}}

---

## scope-of-work-template

# Executive Scope of Work — {{PROJECT_NAME}}

**{{COMPANY}}** | {{TRADE / GC}} | {{DATE}}
Project: {{PROJECT_NAME}}, {{CITY, COUNTY, FL}}
Basis of bid: {{PLAN SET, DATE, REV}}; Addenda {{#}}; Specifications {{SECTIONS}}

---

## 1. Project understanding (executive summary)
2–4 sentences: what the project is, our role, and the headline of what we're carrying.

## 2. Inclusions (what we ARE providing)
Organized by CSI division. Be specific and quantity-anchored where useful.
- **Div 03 — Concrete:** {{…}}
- **Div XX — …:** {{…}}

## 3. Exclusions (what we are NOT providing)
- {{Explicit, unambiguous. Every common scope-gap item is named as included OR excluded.}}

## 4. Clarifications & qualifications
- Basis of bid is the documents listed above; addenda {{#}} acknowledged.
- {{Working hours, phasing, site access, laydown, hoisting assumptions.}}
- {{Permit/fees by whom; testing & special inspections by whom.}}
- Florida lien-law (Ch. 713) notices reserved; {{bond/insurance posture}}.

## 5. Assumptions
- {{Geotech, existing conditions, schedule duration, escalation window, quote validity.}}

## 6. Allowances
| # | Description | Amount | Basis |
|---|-------------|-------:|-------|

## 7. Alternates
| # | Description | Add / Deduct |
|---|-------------|-------------:|

## 8. Unit prices
| # | Item | Unit | Price |
|---|------|------|------:|

## 9. Value-engineering options (optional)
- {{Idea — cost/schedule/quality trade-off.}}

## 10. Florida code posture (confirm carried)
- Wind/impact products (NOA/FL#), flood provisions, termite treatment, energy testing,
  threshold inspection (if applicable). State who carries each.

---

## estimate-workbook

# Estimate Workbook — data schema

The `cost-estimator` agent produces two CSVs in the project folder, then runs
`estimating/scripts/build_estimate_xlsx.py` to generate a formatted, formula-driven
`estimate.xlsx`. Keeping the source as CSV makes the estimate diff-able and lets the
auditor recompute everything independently.

## `lineitems.csv`

One row per estimate line. Costs are **unit costs** ($ per unit). Leave unused cost
columns blank/0. Use **either** self-perform (mat/lab/equip) **or** subcontract (sub),
not both, on a given line.

```
division,section,item,description,qty,unit,unit_mat,unit_lab,unit_equip,unit_sub,waste_pct,notes
03,03 30 00,Slab-on-grade 5",4500 SF SOG w/ 6x6 WWM,4500,SF,2.85,1.10,0.20,,7,verify TO off S-201
08,08 51 13,Impact windows,Alum impact-rated NOA windows,38,EA,,,,1450,0,sub incl install
31,31 23 00,Termite soil treatment,Subterranean termite pretreat,4500,SF,,,,0.18,0,FBC required
```

| Column | Meaning |
|--------|---------|
| division | CSI division number (e.g., 03) |
| section | CSI section (optional, e.g., 03 30 00) |
| item | short label |
| description | full description |
| qty | quantity |
| unit | unit of measure |
| unit_mat | material $/unit (pre-tax) |
| unit_lab | labor $/unit (incl. burden) |
| unit_equip | equipment $/unit |
| unit_sub | subcontract $/unit (already includes sub OH&P) |
| waste_pct | material waste %, applied to material only |
| notes | source/assumption |

## `markups.csv`

`key,value` pairs (value in **percent**, e.g., `10` = 10%). Applied in this order:
direct cost → +GCs → +contingency → +insurance → +bond → +permit → +OH&P. Material
sales tax is applied to **material extensions only**.

```
key,value
material_sales_tax_pct,7.0
general_conditions_pct,10
contingency_pct,3
insurance_pct,1.0
bond_pct,1.5
permit_pct,1.0
ohp_pct,8
```

> OH&P applies to GC self-performed work + GCs; **do not** re-mark-up subcontractor
> lines beyond the GC fee the company actually adds. If the company's policy differs,
> note it. Confirm whether bond/insurance/permit sit inside or outside OH&P.

## Output: `estimate.xlsx`

- **Detail** sheet — every line with computed material (incl. waste + tax), labor,
  equipment, sub, and a row total, via live formulas.
- **Summary** sheet — subtotals by CSI division, then the markup waterfall to the bid
  total, all as formulas referencing Detail.

Run:
```
python estimating/scripts/build_estimate_xlsx.py estimating/projects/<project>/
```

---

## bid-proposal-template

# Bid Proposal — {{PROJECT_NAME}}

{{COMPANY LETTERHEAD}}
{{DATE}}

To: {{RECIPIENT / GC / OWNER}}
Re: **{{PROJECT_NAME}}**, {{ADDRESS, CITY, COUNTY, FL}}

Dear {{NAME}},

{{COMPANY}} is pleased to submit our proposal for the {{TRADE / scope}} on the
above-referenced project, based on the documents listed below.

## Basis of proposal
- Drawings: {{SET NAME}}, dated {{DATE}}, rev {{REV}}
- Specifications: {{SECTIONS}}
- Addenda acknowledged: {{#1 dated …, #2 …}}

## Proposed price
| Item | Amount |
|------|-------:|
| **Base Bid** | **${{TOTAL}}** |
| Alternate 1 — {{desc}} | {{add/deduct}} |
| Alternate 2 — {{desc}} | {{add/deduct}} |

Allowances and unit prices per the attached scope of work.

## Schedule
- Proposed duration: {{___ }} ; mobilization within {{___}} of NTP.
- Price valid for **{{30}} days** (material escalation reserved beyond).

## Inclusions / Exclusions
See attached **Executive Scope of Work** — inclusions, exclusions, clarifications,
assumptions, allowances, alternates, and unit prices govern this proposal.

## Qualifications
- Bonds: {{included / excluded — payment & performance at __%}}.
- Insurance: {{GL / builder's risk posture}}.
- Permits & fees: {{by whom}}. Testing & special inspections: {{by whom}}.
- Florida lien-law (Ch. 713) notices reserved. License #: {{DBPR #}}.

We appreciate the opportunity to bid and welcome a scope review.

Sincerely,
{{NAME, TITLE}} — {{COMPANY}} — {{PHONE / EMAIL}}

---

## audit-checklist

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
