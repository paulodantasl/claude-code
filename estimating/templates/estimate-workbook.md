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
