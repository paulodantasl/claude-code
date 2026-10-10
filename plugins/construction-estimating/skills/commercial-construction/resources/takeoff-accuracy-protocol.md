# Takeoff Accuracy Protocol

Mandatory quality gates for every quantity takeoff. These rules exist because each one
maps to a **real observed failure mode** — the kind that swings a bid by 5–60%. Follow
them in order; the takeoff is not done until the QA block at the end is complete.

**Order of work:** build the sheet index (§9) and pass the scale gate (§10) on every
sheet you will measure **before** taking any quantity off it. Then §1–§8 and §11–§13.
Close with the QA block (§14) and run `validate_takeoff.py` (§15).

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
6. **Symbol + tag must agree.** A device counts only when the drawn symbol AND its tag/
   mark (e.g., "T1", "W3", "F-2") agree with the schedule row. A symbol with no tag, a
   tag with no symbol, or a bare mention in a general note ("provide smoke detectors per
   code") is **not** a count — it goes to the Withheld list (§12) or an RFI.
7. **Schedule ↔ plan reconciliation.** A schedule row with no drawn instance, or a
   drawn instance with no schedule row, is an RFI — never silently dropped or added.

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
- Printed dims over the scale; a verified scale (§10) over PDF page scaling; anything
  scaled is `approx`.

## 8. Confidence + reasonableness gates

Every line: `med-high` (measured from printed dims / counted with recount) · `med`
(schedule) · `approx` (derived/scaled) · `assumed` · `RFI`.

**Confidence is a review prioritizer, not an accuracy claim.** `med-high` means "nothing
to flag", not "verified". Review `RFI` → `assumed` → `approx` lines first, largest $
first. Each step down should have a stated reason in Notes (scaled off raster, single
source, congested cluster, schedule-only, etc.).

Then run the ratio screen (§13) and explain any outlier **in writing** before release.

## 9. Sheet index & coverage (before measuring anything)

Build a sheet index from the set's cover/index sheet **and** the actual pages (they
disagree more often than you'd think — missing floors, duplicate sheets, superseded
revs). One row per sheet:

| Sheet | Title | Role | Rev | Read? | Notes |
|---|---|---|---|---|---|

- **Role:** plan · schedule · elevation · section · detail · notes · civil · structural ·
  MEP · spec · calc · cover.
- **Read?:** `read` · `partial` (say what wasn't) · `not read` (say why) · `N/A`.
- Record the **revision / delta** on each sheet (Δ, REV, cloud). If two sets exist, name
  the governing set; superseded sheets are `N/A — superseded by <set>`.
- **Coverage rule:** every quantity's source sheet must be in the index, and every
  `plan`/`structural` sheet must be `read` or carry a reason. An index listing sheets
  that are absent from the PDF (or vice-versa) is an RFI.

## 10. Scale gate (per sheet — no verified scale, no measurement)

A sheet's scale is a **gate, not a default.** Before scaling anything off a sheet:

1. **Find the stated scale and cite where it came from:** `title-block` · `viewport-note`
   (the scale under a drawing title) · `scale-bar` · `calibrated` (from a printed dim) ·
   `NTS`. The title-block note governs the main plan; a viewport note governs its own
   drawing (details and enlarged plans often differ). Several conflicting notes with no
   title-block note → **ambiguous**: calibrate from a printed dimension or don't scale.
2. **Check-dimension test — every sheet.** Measure one long printed dimension (prefer an
   overall, ≥20′) at the stated scale and compare to the printed value:

   | Δ = (measured − printed) ÷ printed | Status | Action |
   |---|---|---|
   | ≤ 1% | `confirmed` | Measure at stated scale |
   | > 1% to ≤ 5% | `amber` | Recalibrate from the printed dim; note it; scaled lines `approx` |
   | > 5% | `red` | Sheet is off-scale (half-size plot, 94.4% plot, wrong viewport) — **recalibrate before any measurement**; never use the stated scale |

   Real failure: an A2.0 plotted at **94.4%** of nominal ¼″ — every scaled quantity on
   it would have been 5.6% low. It happened twice on the same job.
3. **NTS sheets** (diagrams, some details): never scale. Quantities come from printed
   dims or schedules only.
4. Log the result in the takeoff's **Scale log** table (template). A sheet that sources
   a measured/scaled line without a `confirmed`/`amber`(recalibrated) entry fails QA.

## 11. Measurement conventions

**Areas (floors, finishes, slabs):**
- State gross vs net (§6). For **finish areas**, trace the **inside face of the
  enclosing walls**; casework, fixtures, hatch, dimension lines and text are never the
  boundary (finish runs under casework unless the spec says otherwise — state it).
- At doors and cased openings, carry the finish **to the wall centerline** (≈0.75 SF per
  3′ door in a 6″ wall — adds up on a 40-door floor). Windows don't break the boundary.
- Wrap columns, chases and pilasters (deduct when > the §6 deduction threshold).
- A finish change is two areas sharing one transition line — no gap, no overlap. Sum of
  finish areas must close to the floor plate within ~2% (§3).
- **Finish/material comes from the schedule row**, not the plan tag; the tag is the
  cross-check. Tag ≠ schedule → RFI.
- Curved walls are measured as arcs (r × θ), never as chords.

**Linear & derived quantities carry their inputs.** Write the derivation into Notes so
anyone can re-run it:
- Base/trim LF = room perimeter − **stated** door openings (list them; never guess).
- Wall SF = LF × height, with **height bands** where faces step (e.g., "209.33 LF ×
  13′-0″ GF = 2,721.3 SF gross").
- Volumes: area × depth (or LF × section) ÷ 27 = CY — the section must be cited.

**Waste goes on the order quantity, never on the measured quantity.** The takeoff
reports **measured** (net or gross, declared). Waste lives in `waste_pct` (estimate) or
in an order-qty column — never baked into Qty. Order units round **up**:
`order = ceil(measured × (1 + waste) ÷ coverage)` (e.g., sheets, boxes, rolls, bags).

## 12. Withheld items (never fold ambiguity into totals)

Anything you found but cannot quantify with confidence goes in the takeoff's
**Withheld** table — not in the quantities table and not in the seed CSV:

| ID | Item | Location (sheet / grid) | Why withheld | Candidate qty | Resolution (RFI #) |
|---|---|---|---|---|---|

Typical entries: near-match symbols (looks like a W3 but no tag), a schedule row with no
drawn instance, an open alcove with no stated finish convention, a cluster you can't
resolve at max DPI, a detail referenced but not in the set. **Candidate qty** may be
shown so the estimator can size an allowance — but the line is priced only after the
RFI resolves or the estimator moves it in explicitly as an ALLOW line. Withheld IDs must
never appear in `lineitems.csv`.

## 13. Ratio screen (reasonableness — explain every outlier in writing)

Screening bands, Florida-typical. Outside the band ≠ wrong; it means **explain it** (or
find the error). `validate_takeoff.py` computes the starred ratios automatically from
the seed CSV when it can identify the lines.

| Ratio | Typical | Screen (WARN outside) |
|---|---|---|
| ★ Rebar lb per CY of structural concrete | 80–200 (SOG w/ WWM lower; columns higher) | 40–300 |
| ★ CMU units per SF of CMU wall (8×16 face) | 1.125 | 1.05–1.20 |
| ★ HVAC SF of conditioned area per ton — residential | 450–700 | 350–850 |
| ★ HVAC SF per ton — commercial / TI | 250–400 | 200–500 |
| ★ Gypsum board SF per SF of floor — residential | 3.0–4.0 | 2.5–4.5 |
| ★ Gypsum board SF per SF of floor — commercial / TI | 2.0–4.0 | 1.5–5.0 |
| Roof area ÷ footprint (pitched, incl. overhangs) | 1.10–1.35 | 1.05–1.45 |
| Roof area ÷ footprint (low-slope) | 1.00–1.08 | 1.00–1.12 |
| SOG concrete CY per 100 SF at 4″ / 5″ / 6″ (no waste) | 1.23 / 1.54 / 1.85 | exact geometry |
| Mortar CF per 100 CMU | ~8.5 | 7–10 |
| Paint SF (walls+ceilings) per SF of floor — residential | 3.5–4.5 | 3.0–5.0 |
| Duct lb per SF of floor — commercial | 0.8–1.5 | 0.5–2.0 |

For the starred ratios, the validator needs the **gross floor area** in the takeoff
header (`Gross floor area`) and recognizable item names (rebar/reinforcing, CMU/block,
gyp/drywall, HVAC/AC/heat pump/condenser/RTU in TON).

## 14. Takeoff QA block (append to every takeoff — all boxes or it isn't done)

```
□ Sheet index complete; every plan/structural sheet read or reason given
□ Scale gate passed on every sheet measured (check-dim Δ logged; red sheets recalibrated)
□ Layout enumerated from plan graphics (not calc/text extraction alone)
□ Two-direction recount reconciled for every counted item ≥2% of division cost
□ Dimension-string closure checked on all lines used
□ Every schedule read to the last column/footnote; transcribed verbatim
□ "What must exist" sweep complete — every item quantified/excluded/N-A with reason
□ Gross vs net stated for every area; deduction rule named
□ All conflicts logged as RFIs with both values + $ swing
□ Counts require symbol + tag agreement; schedule ↔ plan reconciled
□ Congested-area tolerances declared (± and where)
□ Ambiguous items in the Withheld table — none folded into totals or the seed CSV
□ Measured qty excludes waste; derivations (perimeter − openings, LF × height) in Notes
□ Ratio checks run; outliers explained
□ Illegible/unread items listed (not guessed)
□ Confidence flag on every line; single-source lines flagged
□ validate_takeoff.py run — 0 FAIL (WARNs explained)
```

Mark a box `☑` / `[x]` when done. A box that can't be met stays `□` with a reason on
the same line, flagged `FAILED:` / `NOT MET:` / `N/A:`
(`□ Ratio checks run — FAILED: no GFA on set, RFI-07`). The validator FAILs an
unchecked box with no flagged reason.

## 15. Machine check — `validate_takeoff.py`

```
python3 <scripts>/validate_takeoff.py <project_dir> [--sector residential|commercial|ti|public]
                                      [--golden golden.csv] [--strict]
```

Reads `takeoff.md` (+ `lineitems.csv` if present) and checks: required sections; sheet
index coverage; scale log (recomputes each check-dim Δ and grades it 1% / 5%); every
quantity line has an ID, numeric qty (or RFI), unit, gross/net on areas, source sheet in
the index, method and confidence from the allowed sets (`scaled` ⇒ `approx`); unique
IDs; Withheld IDs absent from the CSV; takeoff ↔ seed-CSV tie-out by `line_id`; QA-block
completeness; the §13 ratio screen; and, with `--golden`, a regression compare against
verified quantities. Exit 1 on any FAIL (`--strict`: WARNs too).
