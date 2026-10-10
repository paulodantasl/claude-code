# Construction Estimating — Deliverable Templates

Copies of the 5 template skeletons the specialist roles fill in.
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
| Gross floor area | {{GFA}} SF |
| Wind / Flood | V_ult {{___}} mph, Risk Cat {{___}}; Flood zone {{___}}, DFE {{___}} |

> Keep the section headings below exactly as written — the validator (Claude Code) finds
> the tables by heading. Column order matters; add columns only at the end.

## Sheet index

> Every sheet in the set (protocol §9). Role: plan / schedule / elevation / section /
> detail / notes / civil / structural / MEP / spec / calc / cover. Read?: read /
> partial / not read / N/A — give a reason for anything but `read`.

| Sheet | Title | Role | Rev | Read? | Notes |
|-------|-------|------|-----|-------|-------|
| A1.0 | Floor plans | plan | 2 | read | |
| … | | | | | |

## Scale log

> One row per sheet you measured or scaled from (protocol §10). Scale source:
> title-block / viewport-note / scale-bar / calibrated / NTS. Check dims in feet-inches
> (`40'-0"`) or decimal feet. Status: confirmed (≤1%) / amber (≤5%, recalibrated) /
> red (>5%, recalibrated) / NTS. The validator recomputes Δ.

| Sheet | Stated scale | Scale source | Check dim (printed) | Check dim (measured) | Δ % | Status |
|-------|--------------|--------------|---------------------|----------------------|----:|--------|
| A1.0 | 1/4" = 1'-0" | title-block | 40'-0" | 40'-1" | 0.2 | confirmed |

## Quantities by CSI division

> One row per measurable/countable item. ID is unique and carried into
> `lineitems.csv` as `line_id`. Qty is **measured** (no waste). Gross/Net is required on
> SF/SY lines (`gross` / `net` / `-`). Method: measured / counted / calculated /
> imported / scaled. Confidence: med-high / med / approx / assumed / RFI — `scaled`
> lines are always `approx`. Put derivations (perimeter − openings, LF × height) in Notes.

| ID | Div | Item | Qty | Unit | Gross/Net | Source (sheet) | Method | Confidence | Notes |
|----|-----|------|----:|------|-----------|----------------|--------|------------|-------|
| 03-001 | 03 | Slab-on-grade, 5" | 4500 | SF | net | S-201 | measured | med-high | 60'-0" x 75'-0" printed dims |
| … | | | | | | | | | |

## Withheld

> Found but not quantifiable with confidence (protocol §12). NOT in the totals above and
> NOT in `lineitems.csv`. Candidate qty is for allowance sizing only.

| ID | Item | Location (sheet / grid) | Why withheld | Candidate qty | Resolution (RFI #) |
|----|------|-------------------------|--------------|---------------|--------------------|
| W-01 | {{e.g., near-match fixture symbol, no tag}} | {{P-101 / C-4}} | {{no schedule row}} | {{1 EA}} | {{RFI-03}} |

## Assumptions

- {{e.g., No geotech provided — assumed spread footings, no dewatering.}}

## Exclusions from this takeoff

- {{Items not quantified and why.}}

## RFIs / clarifications needed

- {{Conflicts between drawings and specs; missing details; illegible scales — both values + $ swing.}}

## Quantity reasonableness checks

- {{Protocol §13 ratios, e.g., rebar 110 lb/CY — within 80–200; CMU 1.125 units/SF — OK.}}

## Takeoff QA block

> Paste the QA block from protocol §14. Mark each box `☑` or `[x]`; an unmet box stays
> `□` with the reason on the same line.

## Seed CSV for the estimator

`lineitems.csv` — core 12 columns + provenance tail, cost columns blank, one row per
quantity ID, no rollup/total rows, no Withheld IDs:

```
division,section,item,description,qty,unit,unit_mat,unit_lab,unit_equip,unit_sub,waste_pct,notes,line_id,source_sheet,method,confidence,price_basis
03,03 30 00,Slab-on-grade 5",4500 SF SOG w/ 6x6 WWM,4500,SF,,,,,,net; printed dims,03-001,S-201,measured,med-high,
```

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
the plugin's bundled `build_estimate_xlsx.py` to generate a formatted, formula-driven
`estimate.xlsx`. Keeping the source as CSV makes the estimate diff-able and lets the
auditor recompute everything independently.

## `lineitems.csv`

One row per estimate line. Costs are **unit costs** ($ per unit). Leave unused cost
columns blank/0. Use **either** self-perform (mat/lab/equip) **or** subcontract (sub),
not both, on a given line.

```
division,section,item,description,qty,unit,unit_mat,unit_lab,unit_equip,unit_sub,waste_pct,notes,line_id,source_sheet,method,confidence,price_basis
03,03 30 00,Slab-on-grade 5",4500 SF SOG w/ 6x6 WWM,4500,SF,2.85,1.10,0.20,,7,net; verify TO off S-201,03-001,S-201,measured,med-high,budgetary
08,08 51 13,Impact windows,Alum impact-rated NOA windows,38,EA,,,,1450,0,sub incl install,08-001,A-501,counted,med-high,quote
31,31 23 00,Termite soil treatment,Subterranean termite pretreat,4500,SF,,,,0.18,0,FBC required,31-001,S-201,calculated,med,sourced
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
| line_id | takeoff ID this line prices (from `takeoff.md`); blank only for Div 01 / estimator-added lines. Join key for procurement |
| source_sheet | sheet(s) the qty came from (carried from the takeoff) |
| method | measured / counted / calculated / imported / scaled |
| confidence | med-high / med / approx / assumed / RFI — a review prioritizer, not an accuracy claim |
| price_basis | sourced (cited web/catalog) / quote (written vendor/sub quote) / budgetary (estimator judgment) / allowance — required on every priced line |

The last five columns are the **provenance tail**. The validator also accepts the
legacy 12-column header, but new work uses all 17 so the takeoff → estimate →
procurement chain stays traceable (`validate_takeoff.py` ties `line_id` + qty back to
`takeoff.md`). Qty is the **measured** takeoff qty — waste goes in `waste_pct`, never in
`qty`.

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
# chat-only mode: produce lineitems.csv + markups.csv and the totals table;
# workbook build runs in Claude Code via the plugin's bundled build_estimate_xlsx.py
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

**Mechanical / protocol gates (run these, don't eyeball them)**
- [ ] `validate_estimate.py --sector <sector>` run on the workbook inputs — PASS (attach output)
- [ ] `validate_takeoff.py --sector <sector>` run on the takeoff — 0 FAIL (attach output); scale log, sheet coverage, Withheld kept out, takeoff ↔ CSV `line_id` tie-out
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
- [ ] Quantity ratios inside the takeoff protocol §13 screen (rebar lb/CY, CMU/SF, SF/ton, gyp/SF, roof/footprint); outliers explained
- [ ] Every priced line carries `price_basis` (sourced / quote / budgetary / allowance); budgetary lines on the largest $ flagged for quotes
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
