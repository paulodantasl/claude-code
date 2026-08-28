# Takeoff Accuracy Protocol

Mandatory quality gates for every quantity takeoff. These rules exist because each one
maps to a **real observed failure mode** — the kind that swings a bid by 5–60%. Follow
them in order; the takeoff is not done until the QA block at the end is complete.

> Case study baseline (655 115th Ave): a calc-derived takeoff showed **237.67 LF** of
> grade beam (5 lines). The dimensioned plan showed **~655 LF (13 lines)** — a **63%
> undercount** — plus a slab-on-grade the calc package never mentioned and **2 middle
> bars per beam** the calc omitted. Concrete went 25.8 → 123 CY. Every rule below traces
> to a miss like that.

## 1. Source hierarchy & triangulation

Rank sources; never let a lower-rank source overrule a higher one:

| Rank | Source | Use for |
|---|---|---|
| 1 | **Dimensioned plan graphics** (the drawn layout + printed dims) | Layout, counts, lengths — GOVERNS |
| 2 | **Schedules & general notes** on the drawings | Sizes, reinforcing, materials, assemblies |
| 3 | **Specifications** | Quality/products (specs govern quality, drawings govern quantity) |
| 4 | **Engineering calcs** | Design basis, load verification — NEVER layout completeness |
| 5 | **Scaling off raster PDFs** | Last resort; always tagged `approx` |

- **Two-source rule:** every quantity that drives >2% of expected division cost must be
  confirmed by **two independent sources** (e.g., plan count + schedule count; plan dims
  + area tabulation). One source → flag `single-source` in the notes.
- **Calc packages are NOT layouts.** Calcs print *representative* members (the 5-of-13
  failure). Enumerate from plan graphics; use calcs only to verify member sizes.
- **Conflicts become RFIs, never silent picks.** Show both values, price the governing
  one, state the swing (e.g., "slab 6″ callout vs 8″ Gen-Note 4 → 47.9 vs 63.9 CY, RFI").

## 2. Counting protocol (grid-walk + two-direction recount)

For every counted item (piles, columns, fixtures, openings, straps, cells):
1. **Lock the grid** from the perimeter dimension strings before counting anything.
2. **Walk each grid line** — count intersections, then mid-span items per line, keeping a
   per-line tally (auditable — someone must be able to re-add your tally).
3. **Recount along the other axis** (count rows, then count columns). The two totals
   must reconcile. If they don't, find the discrepancy — do not average.
4. **Congested areas** (cores, pits, chases, equipment rooms): count separately, at max
   render resolution, and declare a ± tolerance if symbols overlap (e.g., "pit cluster
   7 ±2 — verify against enlarged detail"). Never fold an uncertain cluster silently
   into a confident total.
5. **Cross-check against any independent total**: reaction-table node count, fixture
   schedule rows, panel circuit count, door/window tags on elevations.

## 3. Dimension-string closure

- Partial dimensions along a line must **sum to the overall dimension**. Check closure on
  every line you use. Non-closure = misread or plan error → resolve or RFI.
- Areas: room/space areas must sum to within ~2% of the tabulated floor plate. Beyond
  that, re-measure before proceeding.
- Section area × traced length must reproduce your volume (LF × section = CY foots).

## 4. Full-schedule read (the middle-bar rule)

Read **every column and every footnote** of every schedule — the money hides at the
edges: middle bars ("3 top & bottom **+ 2 middle**"), "add #5 per additional 6″ of
depth" notes, added top steel at supports, alternate-member callouts, remarks columns.
Transcribe schedules verbatim into the takeoff before deriving anything from them.

## 5. "What must exist" completeness sweep

Before closing a takeoff, walk this list and mark each item **quantified / excluded /
N/A with reason**. These are the items real takeoffs silently miss:

- **Below/at grade:** SOG + vapor barrier + sand fill, termite treatment, dewatering,
  pile cutoffs, waterproofing/dampproofing, under-slab MEP, flood vents (AE/VE zones).
- **Concrete/masonry:** formwork, embeds/plates/anchor bolts/dowels, middle bars, added
  top steel, laps/hooks (≥10% on longitudinal), filled cells + grout, joint reinforcing,
  lintels, interior (not just perimeter) tie beams.
- **Framing/envelope:** blocking, sheathing **with nailing schedule**, hurricane
  connectors **both ends**, sealed-deck underlayment, parapet flashing/coping, sealants,
  firestopping, insulation **by assembly type** (they differ — R-30 foam vs R-11 batt).
- **Openings:** count from plans AND elevations; impact/NOA where WBDR; garage +
  secondary overhead doors; access panels.
- **MEP:** equipment pads, condensate, refrigerant line sets, roof penetrations/curbs,
  panel/breaker counts vs schedules, low-voltage, smoke/CO devices.
- **Site:** driveway/walks, fence/barriers (pool barrier!), landscape/irrigation, final
  grading.
- **By-others/allowance scope** (stairs, railings, elevator, pool, trusses): carried as
  ALLOW lines with named scope — not dropped.

## 6. Gross vs net discipline

State explicitly whether each area/wall quantity is **gross or net of openings**, and
which deduction rule you used (e.g., masonry: deduct openings > 10 SF). A gross number
handed to an estimator without the label becomes a silent overprice — and the credit
shows up at buyout, in the sub's favor, not yours.

## 7. Render & read discipline (raster plans)

- Render at **300+ DPI in tiles**; read schedules/notes/legends FIRST (cheap, dense),
  then plan quadrants.
- **Never conclude "absent" from a low-DPI read.** "Not found at the resolution read" is
  an RFI, not an exclusion.
- **Write output early and incrementally.** Produce the takeoff table as you complete
  each division — never hold everything for one final write (budget exhaustion after
  reading but before writing = a lost takeoff).
- Record what was **not legible** as its own list. Never fill an illegible cell with a
  plausible value.
- Scale bar over PDF page scaling, printed dims over both; anything scaled is `approx`.

## 8. Confidence + reasonableness gates

Every line: `med-high/measured` · `med` (schedule) · `approx` (derived/scaled) ·
`assumed` · `RFI`. Then run the ratio table (from `estimating-methodology.md`) —
rebar lb/CY, CMU/SF, duct lb/CFM, fixtures/SF, tons/SF, pile spacing — and explain any
outlier **in writing** before release.

## 9. Takeoff QA block (append to every takeoff — all boxes or it isn't done)

```
□ Layout enumerated from plan graphics (not calc/text extraction alone)
□ Two-direction recount reconciled for every counted item ≥2% of division cost
□ Dimension-string closure checked on all lines used
□ Every schedule read to the last column/footnote; transcribed verbatim
□ "What must exist" sweep complete — every item quantified/excluded/N-A with reason
□ Gross vs net stated for every area; deduction rule named
□ All conflicts logged as RFIs with both values + $ swing
□ Congested-area tolerances declared (± and where)
□ Ratio checks run; outliers explained
□ Illegible/unread items listed (not guessed)
□ Confidence flag on every line; single-source lines flagged
```
