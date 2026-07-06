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
> **confidence** flag from the protocol taxonomy: `med-high/measured` · `med`
> (schedule) · `approx` (derived/scaled) · `assumed` · `RFI`. Mark anything scaled
> off a raster PDF as **approx** and recommend verified measurement. For areas,
> state **gross vs net** and the deduction rule; flag **single-source** quantities;
> give congested areas a declared **± tolerance**.

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
- {{Run the band table in takeoff-accuracy-protocol.md §8; explain every out-of-band value.}}

## Takeoff QA block (mandatory — all boxes or the takeoff is not done)

```
□ Layout enumerated from plan graphics (not calc/text extraction alone)
□ Two-direction recount reconciled for every counted item ≥2% of division cost
□ Dimension-string closure checked on all lines used
□ Every schedule read to the last column/footnote; transcribed verbatim
□ "What must exist" sweep complete — every item quantified/excluded/N-A with reason
□ Gross vs net stated for every area; deduction rule named
□ All conflicts logged as RFIs with both values + $ swing
□ Congested-area tolerances declared (± and where)
□ Ratio table in §8 run; every out-of-band value explained in writing
□ Illegible/unread items listed (not guessed)
□ Confidence flag on every line; single-source lines flagged
```
