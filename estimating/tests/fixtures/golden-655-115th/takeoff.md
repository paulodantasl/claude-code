# Quantity Takeoff — 655 115th Ave (regression fixture)

> Fixture for `estimating/tests/`. Quantities are the verified values recorded in the
> Job 2025-227 run log (`jobtread-takeoff-protocol.md` §7 and the protocol case study).
> It exercises every validate_takeoff.py check and must stay PASS-clean.

| Field | Value |
|-------|-------|
| Project | 655 115th Ave |
| Location / AHJ | Treasure Island, Pinellas County, FL |
| Plan set | 04.10 A0.0 set, rev 2 |
| Addenda incorporated | None |
| Takeoff by | takeoff-engineer |
| Date | 2026-07-04 |
| Basis | PDF plans + specs |
| Gross floor area | 5,173.34 SF |
| Wind / Flood | V_ult 150 mph, Risk Cat II; Flood zone AE, DFE 11 |

## Sheet index

| Sheet | Title | Role | Rev | Read? | Notes |
|-------|-------|------|-----|-------|-------|
| A0.0 | Cover / index | cover | 2 | read | |
| A1.0 | GF + FF plans | plan | 2 | read | |
| A2.0 | SF + roof plan | plan | 2 | read | plotted at 94.4% — recalibrated |
| S1 | Foundation plan | structural | 2 | read | |
| S2 | Schedules + gen notes | schedule | 2 | read | |
| M1 | Mechanical plan | MEP | 1 | partial | equipment schedule only — duct layout is delegated design |

## Scale log

| Sheet | Stated scale | Scale source | Check dim (printed) | Check dim (measured) | Δ % | Status |
|-------|--------------|--------------|---------------------|----------------------|----:|--------|
| A1.0 | 1/4" = 1'-0" | title-block | 40'-0" | 40'-0" | 0.0 | confirmed |
| A2.0 | 1/4" = 1'-0" | title-block | 40'-0" | 37'-9 3/8" | 5.6 | red |
| S1 | 1/4" = 1'-0" | viewport-note | 64'-8" | 64'-9" | 0.1 | confirmed |
| S2 | NTS | NTS | | | | NTS |

## Quantities by CSI division

| ID | Div | Item | Qty | Unit | Gross/Net | Source (sheet) | Method | Confidence | Notes |
|----|-----|------|----:|------|-----------|----------------|--------|------------|-------|
| 03-001 | 03 | Grade beam | 655 | LF | - | S1 | measured | med-high | 13 lines from plan graphics; calc showed 5 |
| 03-002 | 03 | Structural concrete, total | 123 | CY | - | S1, S2 | calculated | med | GB section x LF + SOG area x depth |
| 03-003 | 03 | Rebar, grade beams + SOG | 14500 | LBS | - | S2 | calculated | med | incl. 2 middle bars per GB2 |
| 06-001 | 06 | GF footprint / plate | 2586.67 | SF | gross | A1.0 | measured | med-high | |
| 06-002 | 06 | FF footprint / plate | 2586.67 | SF | gross | A1.0 | measured | med-high | |
| 06-003 | 06 | Exterior perimeter | 209.33 | LF | - | A1.0 | measured | med-high | closure checked |
| 06-004 | 06 | GF exterior wall | 2721.3 | SF | gross | A1.0 | calculated | med-high | 209.33 LF x 13'-0" |
| 06-005 | 06 | GF partitions | 96.8 | LF | - | A1.0 | measured | med-high | |
| 06-006 | 06 | FF partitions | 130.0 | LF | - | A1.0 | measured | med-high | |
| 07-001 | 07 | Roof bulkhead | 221.7 | SF | gross | A2.0 | scaled | approx | 8-pt polygon at recalibrated k=17 |
| 08-001 | 08 | Flood vents | 8 | EA | - | A1.0 | counted | med-high | two-direction recount |
| 09-001 | 09 | Gypsum board, walls + ceilings | 17800 | SF | gross | A1.0 | calculated | approx | LF x height per room |
| 23-001 | 23 | HVAC split systems | 9 | TON | - | M1 | counted | med | equipment schedule |

## Withheld

| ID | Item | Location (sheet / grid) | Why withheld | Candidate qty | Resolution (RFI #) |
|----|------|-------------------------|--------------|---------------|--------------------|
| W-01 | Porte-cochère door line | A1.0 / grid 9 | A vs S conflict | 1 EA | RFI-04 |

## Assumptions

- Slab priced at 6" per plan labels; note 4 says eight (6) — RFI-02.

## Exclusions from this takeoff

- Duct layout (delegated design).

## RFIs / clarifications needed

- RFI-02: slab thickness 6" vs 8" (±15 CY).
- RFI-04: porte-cochère door line.

## Quantity reasonableness checks

- Rebar 117.9 lb/CY — within 80–200.

## Takeoff QA block

```
☑ Sheet index complete; every plan/structural sheet read or reason given
☑ Scale gate passed on every sheet measured (check-dim Δ logged; red sheets recalibrated)
☑ Layout enumerated from plan graphics (not calc/text extraction alone)
☑ Two-direction recount reconciled for every counted item ≥2% of division cost
☑ Dimension-string closure checked on all lines used
☑ Every schedule read to the last column/footnote; transcribed verbatim
☑ "What must exist" sweep complete — every item quantified/excluded/N-A with reason
☑ Gross vs net stated for every area; deduction rule named
☑ All conflicts logged as RFIs with both values + $ swing
☑ Counts require symbol + tag agreement; schedule ↔ plan reconciled
☑ Congested-area tolerances declared (± and where)
☑ Ambiguous items in the Withheld table — none folded into totals or the seed CSV
☑ Measured qty excludes waste; derivations (perimeter − openings, LF × height) in Notes
☑ Ratio checks run; outliers explained
☑ Illegible/unread items listed (not guessed)
☑ Confidence flag on every line; single-source lines flagged
☑ validate_takeoff.py run — 0 FAIL (WARNs explained)
```
