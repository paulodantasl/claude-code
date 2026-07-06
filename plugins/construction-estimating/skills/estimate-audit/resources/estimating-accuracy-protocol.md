# Estimating Accuracy Protocol

*(facts as-of: 2026-07 — re-verify dated items: code editions, tax rates, statutes, $/SF bands)*

Mandatory pricing-quality gates layered on top of `estimating-methodology.md`. Each rule
traces to a **real observed failure**: a Div 26 priced at 2.2% of direct when the
benchmark band is 5–8% (a $45–80k hole), a scope that committed **$522k of allowances
while the priced CSV carried $291k**, and steel columns committed in the scope at
**qty = 0** in the estimate. The waterfall math being perfect does not make the estimate
right — coverage and calibration do.

## 1. Division benchmark validation (run before release)

After pricing, compute each division's **% of direct cost** and **$/SF** and compare to
the band for the sector. Any division outside its band → investigate and either fix or
justify **in writing** in the estimate notes. A division at $0 that isn't explicitly
excluded is a finding, not a default. Bands (FL, order-of-magnitude — widen for unusual
programs, see sector profiles for sector-specific overrides). **Two-tier semantics:**
the bands here are the *investigate* threshold you apply by hand; the validator's
coded bands are a looser *WARN floor* — passing the validator does not excuse this
table:

| Div | Scope | Custom res (% of direct) | New commercial | TI/buildout |
|---|---|---|---|---|
| 01 | General reqs (if line-itemed) | 5–10 | 6–12 | 8–15 |
| 03 | Concrete | 6–14 (pile/elevated: to 18) | 8–18 (tilt: to 25) | 0–4 |
| 04 | Masonry | 2–8 | 2–10 | 0–3 |
| 05 | Metals | 1–5 | 4–12 | 1–4 |
| 06 | Wood/plastics | 6–14 | 1–6 | 2–8 (millwork) |
| 07 | Thermal/moisture | 4–9 | 4–8 | 1–4 |
| 08 | Openings | 4–10 (impact coastal: to 12) | 4–10 | 4–10 |
| 09 | Finishes | 12–24 | 8–15 | 20–35 |
| 21–23 | Fire/plumb/HVAC | 8–16 | 12–22 | 15–30 |
| 26–28 | Electrical/low-V | **5–8 res · 8–14 comm/TI** | 8–14 | 10–18 |
| 31–33 | Earthwork/site/utils | 4–12 (piles: to 15) | 8–20 | 0–2 |

**$/SF gates:** compute on conditioned AND gross; compare to the sector band (see sector
profiles); justify outliers in writing. A number inside the band is not proof of
accuracy — but a number outside it is proof you must look again.

## 2. Scope ↔ estimate tie-out matrix (mandatory, two-way)

Build an explicit matrix before release — every row must balance:

| Check | Rule |
|---|---|
| Allowances | Every allowance in the scope narrative has **exactly one** CSV ALLOW row **at the same value**. Totals equal to the dollar. |
| Inclusions | Every scope inclusion maps to ≥1 priced line (or an explicit rollup note). |
| Priced lines | Every priced line is inside the scope narrative (nothing priced-but-unscoped). |
| Exclusions | Nothing excluded in scope carries a price. |
| Alternates/unit prices | Listed in scope ⇔ priced separately, **outside** the base. |
| Cross-deliverable equality | Bid total = proposal price = SOV total = draw-schedule total. Allowance totals equal in every document. |

Any mismatch is a **release blocker** — the scope is contractually inclusive; an
unpriced commitment is free work you just promised.

## 3. Zero-quantity and rollup guards

- **No silent zero-qty rows.** Every `qty = 0` row is one of: (a) an intentional
  info/sanity row **priced at $0 with an explicit note**, or (b) a placeholder that MUST
  be converted to a priced line or a named allowance before release. Grep for them; list
  each with its disposition.
- **Rollup rows never price.** Any "total/rollup (info)" row carries $0 unit costs and a
  do-not-double-count note. The validator checks this mechanically.
- **Waste on material only** — never on labor/equip/sub.

## 4. Sourced vs budgetary calibration

- Label every line's basis: `sourced` (procurement.csv URL+date), `quote` (real sub/vendor
  quote), `budgetary` (banded assumption), `allowance`, `plug`. **Plugs expire** — a plug
  still unlabeled at release becomes a named allowance or gets a quote.
- When `procurement.csv` exists, sourced prices replace budgetary plugs; QUOTE-REQ items
  stay budgetary **and** appear on the RFQ list — the RFQ list in the scope and the
  QUOTE-REQ set in procurement must match.
- Published retail prices are ceilings, not buyout numbers — note the expected trade
  delta rather than inventing it.

## 5. Markup discipline (recap + traps)

- Waterfall applied **once, in order**: direct → material sales tax (on **material
  extensions only**) → GCs → contingency → insurance → bond → permit → OH&P.
- **Subs are never re-burdened** (their OH&P is inside `unit_sub`).
- Bond by contract type: 0% private residential; **required on FL public work
  (255.05)**; per contract otherwise. Retainage per sector (see sector profiles).
- GCs sized to the **actual schedule and staffing**, sanity-checked as a % after.
- Document the contingency posture (whose contingency, covering what) — layered
  GC-contingency + owner-contingency must be deliberate, not accidental.
- Escalation: state the price-validity window; flag commodity-volatile lines
  (lumber, steel, copper, fuel) when the schedule extends past the window.

## 6. Run the deterministic validator

Before calling any estimate done:

```
python3 <scripts>/validate_estimate.py <project_dir>/ [--sector residential|commercial|ti|public]
# <scripts> = estimating/scripts/ in the repo checkout;
#             ${CLAUDE_PLUGIN_ROOT}/scripts/ (or the skill's resources/) on a plugin install
```

It mechanically checks: CSV schema, zero-qty dispositions, rollup pricing, waste
placement, unit whitelist, division benchmark bands, allowance/scope tie-out (when the
scope file is present), and waterfall recompute. **Fix every FAIL; answer every WARN in
writing.** Prompt discipline catches most errors; the validator catches the rest at $0
marginal cost — there is no reason to skip it.

Note: the validator's allowance scan is **best-effort** (±2% tolerance, text
matching against the scope); the to-the-dollar allowance tie-out in §2 remains a
manual matrix check — the scan passing does not satisfy §2.

## 7. Estimator self-audit (before hand-off to the independent auditor)

```
□ Benchmark bands computed; every out-of-band division justified in writing
□ Tie-out matrix built and balanced (allowances to the dollar)
□ Zero-qty rows dispositioned; rollups at $0 with notes
□ Every line labeled sourced/quote/budgetary/allowance/plug; no live plugs
□ validate_estimate.py: PASS (or every WARN answered)
□ Sales tax base = material extensions only; subs not re-burdened
□ Bond/retainage/OH&P posture matches the sector profile
□ Price-validity window stated; volatile commodities flagged
□ FL items priced: impact/NOA, flood, termite, energy testing, threshold (if triggered)
```

The independent audit (estimate-auditor) still runs after this — self-audit is the
floor, not the substitute.
