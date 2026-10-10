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

> Keep the section headings below exactly as written — `validate_takeoff.py` finds the
> tables by heading. Column order matters; add columns only at the end.

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
