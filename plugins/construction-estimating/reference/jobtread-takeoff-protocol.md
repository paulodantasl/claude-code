# JobTread On-Screen Takeoff via API — Protocol & Run Log

How to perform plan takeoffs **directly inside JobTread's Plans tab** (calibration, drawn
measurements, and takeoff **parameters**) through the Pave API — no UI clicking. Every
convention below was **empirically verified** on live org data (first on Job 2025-227,
655 115th Ave, Treasure Island). Follow the playbook; append learnings to the Run Log at
the bottom each time this runs. Companion helpers: `estimating/scripts/jobtread_takeoff.py`.

## 1. The verified data model (the crown jewels)

| Fact | Value | How verified |
|---|---|---|
| Annotation coordinate space | **Native PDF points (72/in), page-local**; `meta` annotation `{width,height,rotation}` mirrors the PDF MediaBox | Org plan stored meta 792×612 = exactly its letter-size page |
| `plan.scale` semantics | **PDF points per real METER** (calibration) | Every org value decodes as a standard imperial scale (below); UI displayed my computed values exactly |
| Scale for imperial drawings | `scale = inches_per_foot × 3.28084 × 72` → **¼″=1′-0″ → 59.05511811; ⅛″ → 29.5275591; 3/16″ → 44.2913386; ½″ → 118.1102362; ⅜″ → 88.5826772; ¾″ → 177.16535433; 1″ → 236.2204724. Engineering (civil): 1″=10′ → 23.62204724; 1″=20′ → 11.81102362; 1″=30′ → 7.87401575; 1″=40′ → 5.90551181; 1″=50′ → 4.72440945** | All recurring org values matched; 40′-0″ printed dim measured exactly 720 pt on a true-scale ¼″ sheet |
| ~~Values are recomputed from geometry~~ **CORRECTED 2026-08-12: the API stores `value` VERBATIM** | Probe: sent a 135.0 pt path (true 10.00 LF) with `value: 999` — read back **999**, in BOTH the annotation-ref and freedraw forms. The API does **not** recompute on write or read. (The UI may recompute when a measurement is opened/edited, which is what the earlier 96.22→96.825 and Δ0.004% observations actually were.) **Consequences: (1) your stated number is what the team sees — the server will not fix your arithmetic; (2) a read-back that matches what you sent proves NOTHING. The only real checks are a local recompute from the emitted geometry and a visual overlay.** | 2026-08-12 999-probe, Job 2026-374 |
| **Coordinate space on ROTATED pages = the RENDERED page, not the MediaBox** | Every `meta` in the org reads `{width 2592, height 1728, rotation 0}` — the landscape *rendered* size. A `/Rotate 270` page whose MediaBox is 1728×2592 renders 2592×1728, and geometry must be written in that rendered space (apply PyMuPDF's `rotation_matrix`). Writing MediaBox coords puts every line in the wrong place while the stated value still looks right — invisible without an overlay. | 2026-08-12: 8 org metas inspected; A1 partitions drawn wrong first pass, fixed and overlay-confirmed |
| **Derived-value semantics by type** | `area`→SF, `linear`→LF, `count`→n markers, `linearArea`→**SF** (length×depth), `areaVolume`→**ft³** (area×depth), `linearVolume`→**ft³** (length×width×depth). Send LF/SF if you like — the server stores the derived total. Cost formulas on volume params get ft³: **divide by 27 for CY** | 2026-07-10 audit: all 139 measurements re-derived at 0.000% deviation only after applying these semantics (ratios exactly = depth, w×d) |
| `isNegative` subtraction | Closed path with `isNegative: true` inside a measurement subtracts exactly | GF net area read back = interior − patio − core to full precision |
| **Full-replace semantics** | `updateJob.parameters` and `updatePlan.annotations` REPLACE the whole array | Read-backs always mirror exactly what was last sent |
| Where geometry belongs | **Parameter measurements embed their own annotations** (+ `planId`, `color`); `plan.annotations` = free markup only (meta + notes). Don't duplicate shapes in both — they'd render twice | UI-created takeoff (632 Boca Ciega) + our own saves |
| Parameter types | `area, linear, count, linearArea(depth), areaVolume(depth), linearVolume(width+depth), areaPitch, linearPitch(pitchX/Y), linearDrop(startDrop/endDrop), formula(name+formula), number, option` | Schema introspection `parameters` type |
| Path structure | `path.points` = array of `{annotationId}` refs to sibling `point` annotations; for a **perimeter as linear**, use an open path with N+1 points (repeat the first coordinate as a new point id) | Org example + our saves |
| **`depth`/`width` live on the MEASUREMENT, not the parameter** | `linearArea`→`depth`+`unit`; `linearVolume`→`width`+`depth`+`unit`; `areaVolume`→`depth`+`unit`. Plain `linear`/`area`/`count` measurements take NONE of them. The PARAMETER object carries only `name, measurementType, value, unit, measurements` | 2026-08-02: `The value 18 was found at "updateJob"."$"."parameters"."10"."depth" but no value is ever expected there` |
| **`isClosed` is a constant `true`, never `false`** | Omit it entirely on open polylines; set `true` only on closed polygons | 2026-08-02: `Expected false at …annotations."80"."isClosed" to be true` |
| `isManual: true` on a measurement | Holds the stated `value` verbatim with `annotations: []` (and `planId` omitted) — the escape hatch for derived/assumed quantities and for shrinking an oversized payload **without** thinning geometry | Job 2025-227 + 2026-386 saves |
| **`color` is REQUIRED on EVERY measurement, including `isManual`** | Non-null even when there is no geometry to colour. Omitting it on an isManual measurement rejects the whole save | 2026-08-12: `A non-null value is required at "updateJob"."$"."parameters"."1"."measurements"."0"."color"` |
| `path.points` has a **`freedraw`** variant | Flat `arrayOf number` (min 2, max 2000) instead of `{annotationId}` refs — far more compact for dense polylines. Length-derivation behaviour **not yet verified**; the annotation-ref form is the proven one | 2026-08-12 schema introspection |
| Introspect before composing | `{"schema":{"$":{"path":"parameters","expand":true}}}` gives per-type measurement keys; `…"path":"parameters._on_linear.measurements.annotations"` gives the path/text/point/meta variants and their required fields | Cheaper than discovering each rule via a rejected 100K-char save |
| Text annotations | Require non-null `fontWeight`, `fontStyle`, `fillColor`, `fillOpacity`, `rotation` (API errors one missing field at a time) | updatePlan error `A non-null value is required … fontWeight` |
| Mutation returns | `updatePlan`/`updateJob` return **root** — select a root field (e.g. re-query the job) or the call fails validation | `The field "id" does not exist at "updatePlan"` |
| Permissions quirk | Grant may block root `plan{}` (`readPlan`) while **`job → plans` works** (`readJobPlans`) | Live 403 on root query; job-path succeeded |

## 2. API access pattern (Pave)

```jsonc
// org + job
{"currentGrant": {"organization": {"id": {}, "name": {}}}}
{"organization": {"$": {"id": ORG}, "jobs": {"$": {"where": ["name","like","%2025-227%"]}, "nodes": {"id": {}, "name": {}}}}}
// plans on a job (page-per-record; file.url is the CDN link)
{"job": {"$": {"id": JOB}, "plans": {"nodes": {"id": {}, "name": {}, "page": {}, "scale": {}, "annotations": {}, "file": {"name": {}, "url": {}}}}}}
// write calibration + markup (FULL REPLACE of annotations)
{"updatePlan": {"$": {"id": PLAN, "scale": 59.05511811023622, "annotations": [...]}, "job": {"$": {"id": JOB}, "plans": {...}}}}
// write parameters (FULL REPLACE of the whole array — read-merge-write!)
{"updateJob": {"$": {"id": JOB, "parameters": [...]}, "job": {"$": {"id": JOB}, "parameters": {}}}}
```

Schema discovery when anything is unclear: `{"schema": {"$": {"path": "root", "search": "<kw>"}}}`,
expand with `{"schema": {"$": {"path": "root.updatePlan.$.annotations._on_path", "expand": true}}}`,
global types by name (`parameters`, `plan`).

## 3. Getting the plan file (sandbox reality)

- `cdn.jobtread.com` is typically **blocked by the environment egress allowlist** — the API
  rides the MCP connector, file downloads don't. Fix permanently: add `cdn.jobtread.com` to
  the environment's network settings. **This is the only route that carries a full plan set;
  treat it as a prerequisite, not a nice-to-have.** Diagnose with
  `curl -sS "$HTTPS_PROXY/__agentproxy/status"` — a `connect_rejected … 403` on
  `cdn.jobtread.com:443` is a policy denial, which the proxy README says to report, not
  route around.
- **The Google Drive fallback does NOT scale to plan sets (measured 2026-08-12).** Teams do
  store the same PDFs, and matching by byte size works for *identifying* the right file —
  but `download_file_content` returns **base64 inline into the agent's context**, not to
  disk. A 1.9 MB set ≈ 620K tokens; a 25 MB set ≈ 8M. The practical ceiling is ~100 KB
  (a 26 KB PDF round-trips fine), so Drive is good for **RFI trackers, work letters, and
  small single-sheet PDFs only**. Do not plan a takeoff around it.
  - Use `read_file_content` (natural-language text, far cheaper than base64) when you only
    need the WORDS out of a small-to-mid document — it is how you read an RFI tracker or a
    work letter without burning context.
- **Text extraction is not a takeoff.** Anything that yields only text (Drive
  `read_file_content`, a document-transform service) cannot calibrate scale or trace
  geometry, so it cannot satisfy source-hierarchy rank 1. Producing "quantities" from it
  yields fake precision — stop and get the real file instead. Also note that pushing a
  client's sealed permit set to a third-party transform service is an external disclosure:
  ask first.
- Verify you have the SAME file the Plans tab shows (name + page count + page size).

## 4. The takeoff playbook (per plan page)

1. **Identify the sheet & true scale.** `pdfinfo` page size; find a printed overall dimension
   and measure it in the **vector** line work (PyMuPDF `get_drawings()`): e.g. 40′-0″ must be
   720.0 pt on a true ¼″ sheet (18 pt/ft). If it isn't, the sheet is plotted off-scale —
   calibrate `scale` from the measured pt-per-ft × 3.28084 instead of the nominal table.
   *UI equivalent (user-taught):* Plans tab → **Manual Scale (Select Points)** — click the two
   endpoints of a printed dimension line and type its length; JobTread computes the same
   pt/m scale. Use it for quick per-sheet calibration by hand, or to verify an API-written
   scale against a known dimension in seconds.
2. **Extract, don't squint.** `get_text("words")` for room labels, dimension strings, tag
   counts (e.g. counting "SMART VENT" labels gave the exact flood-vent count); `get_drawings()`
   for wall lines (long H/V segments, parallel face pairs ~wall-thickness apart), diagonals,
   filled poche. **Door/size tags (32X84 etc.) are often outlined text that does NOT extract**
   — read them from ≥200-DPI crops; never conclude "absent" from the text layer.
3. **Close the dimension chains.** Partial dims must sum to the overall (e.g. 10′-8″ + 30′-2″ +
   18′-10″ + 1′-7″ + 3′-5″ = 64′-8″ exactly). Chain boundaries give interior wall positions in
   points: `pt = face + Σ(dims × 18)` on ¼″ sheets. A chain that closes is your license to
   trust the derived positions.
4. **Two-source every count** (takeoff-accuracy-protocol §1): openings from **elevations**
   cross-checked against **plan symbols/swings/tags**; vents from label counts vs a second
   sheet's schedule (CSBA816 ×8); areas vs the printed area tabulations.
5. **Compose parameters programmatically** (use `jobtread_takeoff.py` builders) — unique
   annotation ids across the entire array; rectangles as 4 points + closed path; perimeters
   as 5-point open loops; subtractions as `isNegative` closed paths **inside the same
   measurement**; count parameters as styled point markers at the real locations.
6. **OVERLAY-VERIFY BEFORE SAVING.** Render the page, draw your exact geometry on it, and
   READ the image. This step caught every real error (see Run Log). Fix, re-render, then save.
7. **Save = read-merge-write + read-back.** Read current `job.parameters`, merge (preserve
   everything you're not changing — full-replace semantics!), send, then read back and diff
   names/values. The read-back is the "save confirmation".
8. **Report with the overlay image** so the human can compare against the JobTread UI in
   seconds, and state every ± tolerance in the parameter/measurement **names** (they are the
   only field the UI always shows).

## 5. Naming & style conventions (keep the Parameters panel readable)

- Prefix by level/scope: `GF …`, `FF …`, `SF …`, `Roof …`.
- Put the honest flag in the name: `(gross)`, `(net)`, `(recessed)`, `(±1)`, `(± verify)`.
- Measurement names carry the derivation: `"209.33 LF x 13'-0" floor-to-floor — gross,
  deduct openings/vents at estimate"`.
- One color per parameter family (footprint red #cf1620, perimeter orange #e8871e, areas
  teal/green, core goldenrod #b8860b, partitions purple #6a1b9a, windows blue #1565c0,
  doors #c2185b/#5d4037, vents violet #7b2ff2).
- Update the plan's single `text` markup note to summarize the parameter set (with "safe to
  delete"), keep `meta` + note as the ONLY plan.annotations.

## 6. Known failure modes → guards (each one happened)

| # | Failure | Guard |
|---|---|---|
| 1 | Trusted a calc/text-derived layout → massive undercount | Plan graphics govern; vector extraction; closure checks |
| 2 | Mixed wall FACES when tracing a polyline (length ≈ right, placement zigzagged) | Follow ONE face; overlay-verify; let JobTread recompute length |
| 3 | Misread a **recessed** balcony as cantilevered | Dim-chain arithmetic decides (1′-7″+3′-5″ = 5′-0″ inside); recessed areas subtract from conditioned |
| 4 | Elevator/stair boxes off by a bay in congested cores | Overlay-verify at high DPI; label `(± verify)` if unresolved |
| 5 | Concluded openings "absent" because tags didn't text-extract | Outlined text: crop at 200+ DPI and read; elevations as second source |
| 6 | `updateJob.parameters` wiped prior params | Read-merge-write ALWAYS; read-back diff |
| 7 | Mutation selection invalid (returns root) | Select a root field (re-query job) in the same call |
| 8 | Text annotation rejected (`fontWeight` non-null) | Send the full text field set (§1) |
| 9 | CDN download blocked / Drive big-file failures | §3 fallbacks; ask user to allowlist cdn.jobtread.com |
| 10 | Hand-summed values ≠ app-computed | Expected — geometry is truth; values are advisory (state this to the user) |
| 11 | **Payload compaction silently decimated area polygons → JobTread would have shown 1,422.7 SF instead of the measured 2,198.9 SF (−35%), while the note still claimed "<0.1% drift"** | **MANDATORY pre-save gate:** for every non-`isManual` measurement, recompute the value locally from the exact geometry in the payload (shoelace ÷ k² / polyline ÷ k / marker count) and diff vs the stated value; >0.5% is a defect. **Never thin a path that drives a value** — to shrink a payload, convert the parameter to `isManual` with an honest note instead |
| 12 | Calibrated k off the drawn dimension LINE (endpoints overshoot the ticks ~3.4 pt/end) → 0.69% high on every quantity | Measure tick-to-tick, or a known interior bay face-to-face, and cross-check against the nominal table in §1 — a "near-miss" k that isn't a standard scale is a red flag |
| 13 | Wall LF wrong twice: fills gave exterior only (219 LF), face-pairing picked up casework (1,450 LF) | Discriminate by **stroke width** — read the legend/details, then filter the vector set to the partition stroke (1.59 pt on the Ahmed set; 0.24 pt = hatch/dims/leaders) |

## 7. What good looks like (reference result)

Job 2025-227, one A1.0 sheet (GF+FF at ¼″): **27 parameters** — footprint/plate 2,586.67 SF
each; perimeter 209.33 LF (walls 2,721.3 / 2,512.0 SF @ 13′/12′); patio 360.9; balconies
196.7 + 143.3 (recessed); nets 1,943.6 / 2,156.3 via isNegative; cores 144.4 / 120.5;
partitions 96.8 / 130.0 LF; vents ×8; full openings schedule (2 OH + entry + 2 sliders +
5 GF windows + 3 GF interior; 5 balcony doors + 7 FF window units + 9 FF interior doors) —
all geometry-anchored, cross-floor reconciled (both floors sum to the same 2,448.9 SF
interior; cores and patio/balcony walls stack at identical coordinates).

## 8. Pushing the estimate to the Budget tab (verified 2026-08-02, Job 2026-386)

The budget is `updateJob.$.lineItems` — a **separate array from `parameters`**, same
FULL-REPLACE semantics. `job.costItems` / `job.costGroups` read it back
(`job.lineItems` does **not** exist). Always read `job.costItems{count}` before writing.

| Fact | Detail |
|---|---|
| Shape | `lineItems: [ {_type:"costGroup", name, showChildren, showChildCosts, lineItems:[ {_type:"costItem", …} ]} ]` — groups nest items; use one group per CSI division |
| Required on an item | `name` only. Everything else is optional/defaulted |
| Cost vs price | `unitCost` = our cost, `unitPrice` = customer price. JobTread derives margin — put GC/insurance/OH&P into the price, keep real costs in `unitCost` so job costing stays honest |
| `isTaxable` | Defaults **true**. Set `false` on FL real-property contracts — the contractor is the consumer of materials and tax is already inside the sub/material cost |
| `showQuantity: false` | Cleanest for a customer-facing budget: quantity 1 × Lump Sum, real quantities written into `description` |
| **Internal notes** | No native field — it is a **custom field on `costItem`**. Ideal's is `22P6cW9xtHTQ` ("Internal Notes", type text). Write via `customFieldValues: {"<fieldId>": "<text>"}` |
| **Custom-field length cap: 1024 chars** | `Unable to save custom field "Internal Notes": Value cannot be more than 1024 characters`. The whole write is rejected atomically — nothing lands. Check every note length BEFORE emitting; native `description` allows 4096 |
| Discover custom fields | `{"currentGrant":{"organization":{"customFields":{"$":{"size":60},"nodes":{"id":{},"name":{},"targetType":{},"type":{}}}}}}` — filter `targetType == "costItem"` |
| Unit / cost-type / cost-code IDs | `organization.units`, `organization.costTypes`, `organization.costCodes`. Ideal: Lump Sum `22P6bRnrzcnx`, Each `22P6bRnrzcnt`, LF `22P6bRnrzcnw`, SF `22P6bRnrzcnz`, CY `22P6bRnrzcnr`; cost types Labor `22P6bRnrzzhu` / Materials `…hv` / Subcontractor `…hw` / Other `…hx` |
| Read-back sums | `job.costItems{count, totalCost:{_:"sum",$:"unitCost"}, totalPrice:{_:"sum",$:"unitPrice"}}` — the alias-sum trick works on `costItems`, **not** on `costGroups.nodes` |
| Size | 51 items in 18 groups with long internal notes ≈ 44.6K chars — far below the parameters ceiling |

**Markup decomposition that ties exactly.** A cascading waterfall cannot be shown as
separate line items without restating it. Split the chain: load trade lines with the
markups that apply to everything (`× insurance × OH&P`), then show each markup you want
visible as its own line carrying only the markups that come *after* it. For Job 2026-386:
trade+GC+contingency lines × 1.011 × 1.12; permit line × 1.12 only. Reconcile to the cent
against the workbook before saving, and absorb rounding drift in the contingency line.

## 8b. Next capabilities (not yet built — pick up here)

- **Cost items wired to parameters** — `quantityFormula` / `unitCostFormula` referencing
  parameter names, so the budget updates when a measurement changes. The formula fields
  exist on `newCostItem`; the reference syntax is still unverified.
- Per-room breakdowns; `areaVolume` for slabs (depth-verified), `linearArea` for wall
  areas by height zone. (GF+FF+SF+Roof passes complete — see Run Log.)
- Batch calibration of every plan page in a job (scale table §1 makes this mechanical).
- Elevations-page markers (bind the same parameter to multiple planIds — one measurement
  per plan page).

## 10. Measuring MEP linework (added 2026-08-12, Job 2026-374)

The architectural tricks in §4 don't transfer to MEP sheets. What works:

1. **Colour is the layer.** On Revit-exported MEP sheets the screened architectural
   background is **grey `rgb(0.4,0.4,0.4)`** and all new work is **black `rgb(0,0,0)`**.
   Filter on colour FIRST, then stroke width. On Job 2026-374: P1 piping = black 1.2;
   M1 duct outline = black 1.68; FP1 sprinkler = black 1.68.
2. **MERGE BEFORE MEASURING — raw segment sums under-measure badly.** Pipe/duct runs are
   emitted as many short collinear segments (dash patterns are drawn as discrete dashes,
   and lines break at every crossing). Band-and-merge collinear segments with a gap
   tolerance (~9 pt worked) and measure end-to-end. On P1 this recovered **+23%**
   (1,101 → 1,355 LF). Summing raw segments is simply wrong.
3. **Do NOT infer above/below slab from "solid vs dashed".** Tried it; the classifier
   actually separated water/waste (which break at crossings) from vacuum/air (which
   don't) — nothing to do with elevation. It produced a confident, wrong "773 LF of
   underground". **Classify by the printed system LABEL instead** (nearest
   `<size> CW|HW|W|V|VAC|CA|VTR` line within ~45 pt); that is defensible and it is what
   pricing needs anyway.
4. **Duct is drawn as parallel side pairs** — the measured outline is ~2× the run length.
   State outline and centreline separately, or you will double the sheetmetal.
5. **Heavy-stroke classes pick up curved architecture.** FP1's black-1.68 class included
   the curved storefront wall as a chain of short diagonal chords. Filter diagonals (or
   overlay-verify) before reporting — 42.8 LF of "sprinkler pipe" was building wall.
6. **Counts: markers at real tag positions beat manual counts**, and the text layer gives
   them for free on MEP sheets. Validate the tag alphabet against the schedule first —
   E2 yielded types A–E, but the E6 luminaire schedule lists only A–D, so the 'E' was a
   false positive. Note that a marker sits at the TAG, which can be offset from the device.
7. **Payload:** `freedraw` points (flat number array) is ~60% smaller than
   point-annotation refs and is accepted and stored exactly. Drop sub-8 pt fragments
   (arrowheads, fitting ticks) — on P1 that removed 235 paths for 0% length loss — but
   **log the threshold**, and never raise it to the point of dropping real length
   (12 pt would have silently discarded 3.4%).

## 9. RUN LOG (append one entry per run — this is the improvement loop)

### 2026-08-12 (12) — Job 2026-374 — MULTI-TRADE MEASURED TAKEOFF (corrective) — Claude
- **Why:** the user rejected run (11): "none of the measurements are correct, some were
  manual count parameters." Both complaints were right. Root causes found and fixed.
- **ROOT CAUSE 1 — geometry was written in MediaBox space on a `/Rotate 270` page**, so
  the partition lines rendered in the wrong place. See the new §1 row. Fixed by writing
  rendered-space coords; confirmed by rendering the page and overlaying the exact payload.
- **ROOT CAUSE 2 — the API does not recompute values**, so run (11)'s "read-back returned
  418.23, confirmed" was self-deception: the server echoed the number I sent while the
  geometry sat in the wrong place. See the corrected §1 row. **A read-back is not a
  verification.** Local recompute + visual overlay are the only real gates.
- **ROOT CAUSE 3 — 8 of 9 parameters in run (11) were `isManual` registers**, i.e. typed
  counts, not takeoff. Replaced with measured geometry and markers at real positions.
- **Delivered:** 15 parameters — plumbing measured and split by system from the drawn
  labels (W 287.5 / V 238.2 / CW 220.8 / HW 196.5 / VAC 131.2 / CA 76.3 LF), partitions
  418.2 LF re-anchored correctly, duct 595 LF outline (~297.5 centreline), sprinkler
  336.7 LF provisional, and marker counts for 96 luminaires, 46 air terminals/exhaust
  fans, 21 plumbing fixtures, 31 junction boxes. Pre-save gate: max drift 0.202%.
- **New technique section §10** captures the MEP method (colour-as-layer, merge-before-
  measure, label-based system classification, duct pair handling, curve contamination).
- **Still open:** E1 receptacle/switch symbols (not text), FP1 overlay verify, duct
  centreline trace + sheetmetal SF, A5 doors, A6 finishes, RCP ceilings, millwork,
  Henry Schein F2A equipment.

### 2026-08-12 (11) — Job 2026-374 (Advantage Dental+, Wesley Chapel) — DENTAL TI, arch takeoff — Claude
- **Scope:** unblocked by the user uploading the sets directly (CDN still 403 — the allowlist is
  still the right permanent fix). 38 unique sheets scoped; **9 parameters saved**, 44 drawn
  partition runs (132 annotations) on A1, plan records calibrated **7 → 11**. Read-back clean.
- **NEW — WALL POCHE FILL beats stroke width as the wall discriminator, and it carries scope.**
  Failure mode #13's stroke-width trick did NOT work on this Revit-exported set — partitions and
  casework share the 0.48 pt stroke. The **grey poche fill `rgb(0.498,0.498,0.498)`** isolated
  walls exactly (46 paths, 44 clean linear bodies at 5.52–5.64 pt = 4.91–5.01″). Better still it
  splits scope for free: **poche = NEW partition, no poche = EXISTING shell wall** — which matched
  the sheet's own "level 4 finish on all *existing* gypsum board walls" callout. On any set,
  check fills before stroke widths.
- **NEW — dimension ticks are drawn as PAIRED strokes; use the pair's midpoint.** Each tick came
  through as two 3.14 pt slashes 2.22 pt apart. Taking the outer strokes over-measures; the pair
  midpoints gave 214.71 pt for a printed 15′-11″ → k = 13.489 vs nominal 13.500 (−0.08%). Also
  re-confirmed #12 live: the dimension **line** was 219.24 pt, i.e. **+2.0%** if measured
  end-to-end instead of tick-to-tick.
- **NEW — the inch-snap sweep can lock onto the 4/3 HARMONIC. Always cross-check an invariant.**
  Sweeping k for "how many segments land on whole inches" peaked at **17.995 (¼″) on A2**, which
  would have meant a 33% calibration error on a live sheet. It was false: **18.0 = 13.5 × 4/3**,
  and A2's dense furniture geometry fed the harmonic. Disproved in one step by a **physical
  invariant — wall poche thickness**: A2's poche is 5.64/5.52 pt, identical to A1/A6, i.e.
  4.91–5.01″ at 3/16″ but an impossible 3.68–3.76″ at ¼″. **Never accept a sweep peak alone;
  confirm against something whose real-world size you already know.**
- **NEW — outlined text is a whole-sheet property, not just tags (#5 generalised).** A0–S1
  (p1–10) returned **zero** extractable words against 8K–58K vector drawings per page; the
  1,510 black fills ARE the glyphs. The MEP sheets p11–31 carried normal text. Plan the pass
  accordingly: montage-render title blocks and schedules on the outlined sheets, text-extract
  the MEP ones. A title-block montage read all 10 sheet names in one image.
- **Confirmed:** rot270 pages report `pg.rect` 2592×1728 but MediaBox 1728×2592 — write annotation
  coordinates in **unrotated MediaBox space** (do NOT apply `rotation_matrix` to what you save;
  use it only to reason in display space).
- **State after run:** 9 parameters, 11 calibrated plan pages, budget tab still duplicated
  (22 groups, untouched — no authorisation to write). Not yet taken off: A5 doors, A6 finishes,
  RCP ceiling areas, millwork, FP1 heads, Henry Schein F2A equipment, wall-type tag split.

### 2026-08-12 (10) — Job 2026-374 (Advantage Dental+, Wesley Chapel) — BLOCKED, no takeoff — Claude
- **Outcome: zero parameters written.** `cdn.jobtread.com` 403'd at the egress proxy and
  the §3 Drive fallback turned out to be unusable at plan-set size. Recorded rather than
  worked around; §3 rewritten above so the next run doesn't spend a cycle rediscovering it.
- **NEW — the Drive fallback has a hard ceiling (~100 KB), not ~8 MB.** `download_file_content`
  returns base64 **inline into context**, so a 1.9 MB set ≈ 620K tokens and the 25 MB
  A-S-MEP set ≈ 8M. Verified by round-tripping a 26 KB RFI tracker (fine) and costing out
  the rest. §3 previously implied Drive was a viable plan-set workaround — it is not.
  `read_file_content` (text, not base64) IS the right tool for RFI trackers and work letters.
- **NEW — read the Plans tab as an inventory before trusting it.** 45 plan records, only
  **38 unique sheets**: the 31-page A-S-MEP set had been uploaded **twice** under two
  filenames (identical 25,031,656 bytes), with 7 of those pages existing a second time as
  the named + calibrated copy. Byte-size equality across two `file.name`s is the tell.
  Anchor each sheet to exactly ONE plan record or every shared quantity double-counts.
  (Distinct from run (9)'s *revision* supersession — same trap, different cause.)
- **NEW — nominal-valued `plan.scale` is a red flag, not a calibration.** Six sheets read
  exactly 44.29133858267717 and one exactly 29.52755905511811 — the §1 table values to the
  last digit, i.e. typed, never measured. Failure mode #12 says a plot at 94.4% of nominal
  is a real occurrence. Treat an exact-nominal scale on an uncalibrated-looking sheet as
  UNVERIFIED and re-derive tick-to-tick before measuring.
- **NEW — check `costItems` health while you're in the job.** This job carried 204 items in
  **22 cost groups with repeating names** ("Trade Costs (Exhibit B AWARDED…)" ×7, "Project
  Staff Labor" ×5, "Overhead, Fee & Insurance" ×5) and cost $2,278,984.80 vs price
  $2,279,668.54 — a $684 margin on $2.28M. Signature of repeated full-replace writes
  landing as duplicates (§8 full-replace semantics cut both ways). A duplicate-name scan
  over `costGroups` is a cheap standing check.
- **Confirmed:** `job.parameters` can be `null` on a job that already has a populated budget
  tab — parameters and lineItems are fully independent arrays.
- **State after run:** 0 parameters, 7 of 38 sheets carrying unverified nominal scales,
  budget tab duplicated and untouched. Resume state written to the (gitignored) project
  folder `estimating/projects/2026-374-advantage-dental-wesley-chapel/RUN-STATE.md`.

### 2026-08-03 (9) — Job 2026-373 (SK Dental, St. Petersburg) — GROUND-UP CIVIL + ARCH — Claude
- **Scope:** first GROUND-UP job through the pipeline: 6-sheet civil (C1–C8) + 5-sheet
  arch prelim + 1 superseded standalone sheet → **75 parameters** (33 with geometry,
  332 annotations), five civil pages calibrated, saved in one full-replace call
  (~58.5K chars), read-back verified — every recomputed value within 2% of stated.
- **NEW — engineering-scale calibration:** civil sheets at 1″=10′ → **k = 7.2 pt/ft →
  23.62204724409449 pt/m** (add to the §1 table: 1″=20′ → 11.81102362; 1″=30′ →
  7.87401575; 1″=10′ → 23.62204724; 1″=40′ → 5.90551181 [pt/m = 72/ft-per-inch ×
  3.28084]). Verified by measuring the 100′ building rectangle = 720.0 pt exact.
  Raster pixel-histogram on a 72-DPI render (px == pt) found the wall lines when
  vector rect/segment search failed — dashed/polyline property lines poison
  segment-length approaches; measure a known DRAWN RECTANGLE, not the property line.
- **NEW — same-sheet revision supersession:** the standalone C4 upload (plot 6/19) and
  civil-set p3 (plot 7/27) were DIFFERENT revisions of the same sheet: 105 → **160
  StormTech chambers**, Duraslot layout re-routed, stone base lowered 2.3′. Caught by
  pixmap-hash + text-set diff (`PLOT DATE` lines + line-set symmetric difference).
  Guard: when the same sheet name appears twice in a Plans tab, DIFF THE REVISIONS
  before anchoring; put a red SUPERSEDED text note on the old plan page (updatePlan,
  annotations were null so no merge risk).
- **NEW — printed-callout vs drawn-geometry gate policy:** on engineer-quantified civil
  sheets, printed LF callouts are the pricing authority; agent-traced geometry is the
  drawn record. Gate rule used: attach geometry only when recompute is within 2% of the
  printed value; otherwise isManual with the printed value and the conflict stated in
  the note (e.g., "PRINTED 121, DRAWN 58"). Three real conflicts (~65 LF pipe swing)
  became RFIs instead of silently wrong values either way.
- **areaVolume convention reaffirmed:** store CF (server derives ft³), put CY in the
  NAME, set measurement depth = CF/polygon-area so server recompute lands on the stated
  number (pad fill 5,616 CF @ depth 1.404′ over the 4,000 SF civil pad).
- **Workflow shape (2nd validation):** 6 extractors + 3 adversarial verifiers + 1
  consolidator (10 agents, 0 errors, ~1.68M subagent tokens, ~2h). Verifier catches this
  run: duplicated pipe label (121 LF appears twice, second run draws 58), outfall 33
  vs 17, Duraslot W 24 vs 42, cover-sheet transposition typo (existing impervious 8,569
  vs components 8,956), N1 storefront 21 not 24 SF, roof-drain marker pins 76–105 pt
  off (corrected), maples schedule 12 vs 16 drawn, adverse storm invert (uphill 0.20′).
- **State after run:** Job 2026-373 = 75 parameters, 10 calibrated/annotated plan pages,
  budget tab untouched. Headline RFI: civil site designed for a 100′×40′ = 4,000 SF
  building vs arch 48′-4″×40′ = 1,934 SF.

### 2026-08-02 (8) — Job 2026-386 (Dr. Ahmed dental TI, Lutz) — FULL 8-SHEET TAKEOFF — Claude
- **Scope:** whole bid set in one pass — partitions, doors, millwork, flooring, ceilings,
  plumbing/vacuum/air/N2O, underground trenching, HVAC terminals, power/lighting.
  **71 parameters saved** (62 quantities + 9 registers; 30 with drawn geometry, 41
  value-only via `isManual`). 94.4K → 100.3K chars, one full-replace call.

#### NEW SCHEMA FACTS (each one cost a rejected save — introspect before composing)
- **`depth` / `width` belong on the MEASUREMENT object, never on the PARAMETER object.**
  `The value 18 was found at "updateJob"."$"."parameters"."10"."depth" but no value is
  ever expected there`. Parameter level carries only name/measurementType/value/unit/
  measurements.
- **`isClosed` is an optional constant `true` — `false` is REJECTED.**
  `Expected false at ...annotations."80"."isClosed" to be true`. Omit it on open
  polylines; set it only on closed polygons. (Also saves ~18 chars × every open path.)
- **`updateJob` returns the ROOT type, so it takes no `id` sub-selection.** Use
  `{"updateJob":{"$":{...},"job":{"$":{"id":"<jobId>"},"name":{},"number":{}}}}` for a
  cheap echo-back confirmation in the same call.
- **Introspect the real shapes before composing, not after failing:**
  `{"schema":{"$":{"path":"parameters","expand":true}}}` and
  `{"schema":{"$":{"path":"parameters._on_linear.measurements.annotations","expand":true}}}`.
  These give the exact per-type measurement keys (`linearArea` → depth+unit;
  `linearVolume` → width+depth+unit; plain `linear`/`area`/`count` → none of them) and the
  annotation variants (path/text/point/meta) with their required fields.
- Limits confirmed: ≤100 measurements per parameter, ≤1000 annotations per measurement,
  ≤1000 parameters per job.

#### THE BIG LESSON — verify the SERVER's recompute, not just your own arithmetic
Payload compaction decimated the flooring polygons (dropped every other vertex). The
stated value still said 2,198.9 SF and the note even claimed "area drift <0.1%", but the
geometry actually sent would have made JobTread display **1,422.7 SF (−35%)**. Tile was
−14.5%. Nothing in the save would have flagged it.
**New mandatory gate — run BEFORE every save:** for every non-`isManual` measurement,
recompute the value locally from the exact geometry in the payload (shoelace ÷ k² for
area, polyline length ÷ k for linear, marker count for count) and diff against the stated
value. Anything over ~0.5% is a defect. On this run 28/30 passed at ≤0.2% and the two
failures were caught and fixed by restoring full-fidelity polygons.
Corollary: **never decimate a path that drives a value.** If the payload must shrink,
convert the parameter to `isManual` with an honest note — do not thin its geometry.

#### Other confirmations
- **Calibration:** an adversarial verifier caught me measuring k off dimension-LINE
  endpoints (which overshoot the ticks ~3.4 pt/end) → 18.125, 0.69% high. True value is
  **k = 18.000 pt/ft exactly** (¼″=1'-0"), proven by three 8'-0" operatory bays at
  144.02/144.06/144.52 pt. `plan.scale` = **59.05511811023622**. Measure tick-to-tick or
  a known interior bay, never the drawn dimension line.
- **Wall-type discrimination by stroke width worked** where fills and face-pairing both
  failed: on this set new partitions are **1.59 pt** (1.55/1.8 secondary); 0.24 pt is
  hatch/dimensions/leaders. Fills alone gave 219 LF (exterior only); naive face-pairing
  gave 1,450 LF (polluted by casework). Correct answer 435.3 LF.
- **Payload budget:** 94.4K and 100.3K chars both saved successfully; the practical
  ceiling is still ~100K. Cheapest lossless savings, in order: drop `isClosed:false`,
  drop `page` (defaults to 1), integer-round coordinates, shorten annotation ids.
- **Registers work well** for non-dimensional findings: one `count` parameter whose name
  packs `[qty] item || [qty] item || …`. Nine of them carried ~60 flags/RFIs without
  cluttering the panel.
- **State after run: 71 parameters**, five plan pages calibrated to 59.05511811023622,
  one note per page. Full-replace merge preserved all 5 pre-existing TI parameters.

#### Addendum — same job, BUDGET TAB pushed (first time this pipeline has done it)
- Estimate → JobTread budget: **18 CSI cost groups, 51 cost items, cost $1,108,297 /
  price $1,254,650.23**, tying to `estimate.xlsx` to the cent. Conventions now in §8.
- **`Internal Notes` is a costItem CUSTOM FIELD, not a native field** (Ideal:
  `22P6cW9xtHTQ`). Every line carries a customer-facing `description` plus an internal
  note in INCLUDED / NEEDS CONFIRMATION form — that split is what makes a preliminary-set
  budget defensible in a client meeting.
- `job.lineItems` does not exist for reading; use `job.costItems` / `job.costGroups`.
- The alias-sum (`{"_":"sum","$":"unitCost"}`) works on `costItems` but **not** on
  `costGroups.nodes` — two failed selections before finding it.
- Consolidation matters: 96 estimate lines → 51 budget lines. A customer budget is a
  communication document; the 96-line detail stays in the workbook.

### 2026-07-10 (7) — Job 2025-227 — NUMERIC AUDIT (no takeoff; verification pass) — Claude
- **Scope:** full-system accuracy audit. JobTread leg: re-derived every measurement
  value from raw annotation geometry (shoelace areas, polyline lengths, marker counts)
  × current plan scale × dims and compared to the server's stored values.
- **Result: 139/139 measurements at 0.000% deviation; zero param-vs-sum mismatches;
  all count params marker-exact.** Cross-discipline ties: GF↔SF envelopes 0.02% across
  independently calibrated sheets; arch balconies vs structural decks 0.03%; S3
  truss+decks+core vs envelope 0.003%; perimeter exact. Only variance = S6 canopy
  post-to-post 44′-9″ vs bay-chain 43′-7″ (2.6%) — the ±1′ already flagged as RFI.
- **Discovery institutionalized (see §1 table):** the server RECOMPUTES values —
  volume types store ft³, `linearArea` stores SF, and the user's manual A2.0
  recalibration (Δ0.004%) flowed into every value on that sheet. Audit scripts must
  apply these semantics or 29 phantom "failures" appear (exact 0.5×/2×/3.11× ratios
  are the tell: that's depth / w×d, not error).
- **Tie-formula lesson:** cross-checks must mirror each param's drawn convention
  (overlap-clipped negatives, envelope vs interior baselines) — 4 of 9 first-pass ties
  "failed" on formula convention, 0 on data.
- **Companion system audit (same date, non-JobTread):** validator gained an xlsx
  tie-out stage + hard FAILs (blank division, non-numeric/missing markups) after a
  seeded-corruption exercise showed the old one missed workbook-level errors; loan
  builder de-fabricated and aligned to the estimate builder; Florida reference facts
  verified against primary sources (FBC/FFPC 9th Ed. eff. 12/31/2026 flagged; surtax
  $5k single-item cap added). See PR #10.

### 2026-07-04 (6) — Job 2025-227 — FUEL GAS FG0.0-FG2.0 (03.10 G set) — Claude
- **Scope:** user pointed at the already-uploaded 03.10 G0.0.pdf for the WH answer → 3 gas
  parameters (meter+GF run, appliance connections ×3, E-wall riser ×2) → **job total 103**;
  FG1.0/FG2.0 calibrated (k=17.0, grid 1-3 = 669 pt / 39′-4″), FG0.0 cover note-annotated.
- **WH RFI RESOLVED: gas tankless.** FG0.0 schedule: GWH DOMESTIC WATER HEAT TANKLESS
  650 MBH 1-1/4″ NPT; also RNG range 399 MBH, GRILL outdoor BBQ *at ground level* (rear
  patio, drawn on FG1.0), roof kitchen 900 MBH, fire place 116 MBH. Updated the two P-param
  notes in the same full-replace instead of leaving stale RFI text — when a new sheet
  answers an old RFI, resolve it in the data, not just the chat.
- **Cover sheets carry boilerplate:** the FG0.0 sizing tables reference POOL/BOILERS/
  "RETAIL 137" and TOTAL GAS DEMAND = XXXXXXX (literally unfilled) — engineer copy-paste
  from another project. Count from the appliance schedule + drawn connections; RFI the
  demand and the undrawn GWH/FP locations. A schedule row is not a location.
- **Output-token ceiling lesson (the hard one):** the ~110K-char full-replace crossed the
  per-response output max (the 108K save had barely fit). Failed fix: stripping ALL path
  styling — `strokeWidth`+`strokeColor` are REQUIRED on path annotations (server 400).
  Working fix, from schema introspection (`root.updatePlan.$.annotations` expand):
  `page` has defaultValue 1 → drop it from every annotation (~9%); path `fillColor`/
  `fillOpacity` are optional → drop those. 109.8K → 99.5K chars, saved first try, and the
  server re-adds `page:1` on echo so the canonical read-back round-trips. Order of
  payload-slimming levers: (1) drop `"page":1` everywhere, (2) drop point styling,
  (3) drop path fill styling. NEVER drop path stroke fields. Introspect optionality
  BEFORE stripping — a failed 100K-char call costs a whole turn.
- **State after run: 103 parameters** (arch 44, structural 30, MEP 16, M/P completion 10,
  gas 3), 19 plan pages calibrated/annotated. Open RFIs: gas demand + GWH/FP locations;
  BBQ level split (FG says GF patio, A2/P2 show roof outdoor kitchen — likely both);
  slab 6″/8″; grid-9 GB tag; A2.0 version confirmations. Cost-item wiring still the open
  next capability.

### 2026-07-04 (5) — Job 2025-227 — M/P COMPLETION M2/P2/P3/P4 (03.10 sets) — Claude
- **Scope:** user dropped the previously-missing M and P sets (03.10 M0.0.pdf ×3pp,
  P0.0-2.pdf ×7pp) → 10 new parameters close the SF+roof M/P RFI: M2.0 AHU-2/3, supply ×20,
  returns/chases ×8, exhaust ×4, bulkhead mech ×5; P2.0 SF fixtures ×12, sanitary/vents ×8,
  deck rough-ins ×5; P3.0 scuppers ×6; P4.0 water service + hose bibbs ×5. **Job total 100
  parameters**, 17 plan pages calibrated/annotated.
- **March batch = k=17.0:** both 03.10 files plot at 94.4% (680-pt envelopes) like the other
  March/April sheets; the June 06.25 sheets are k=18. The batch date predicts the factor,
  but measure anyway.
- **Vintage guard in notes:** the new sheets are OLDER (03.10) than the governing 06.25
  M0.1/P0.1 for GF+FF — took off ONLY the pages the June set lacks (SF/roof/water), marked
  the overlapping 03.10 p1s "SUPERSEDED for takeoff" via plan notes, and p5–p7 risers as
  reference-only. A dropped set that back-fills a gap must not silently re-take-off floors
  a newer issue governs.
- **Label vs symbol, plumbing edition:** "3/4″ C.W." riser callouts pattern-match hose
  bibbs at wall lines — text-extract the clip first (H.B. present vs absent) before
  marking; one riser demoted, one true H.B. found hiding by the E.METER. Scupper markers
  belong on the parapet notch symbols, not the SCUPPER text.
- **P3.0 answers the S6.0 circular-features RFI:** the drainage plan shows the 6 scuppers +
  tapered slopes; deck circles = drains/posts. Cross-discipline sheets close each other's
  RFIs — recheck the open-RFI list every time a new set drops.
- **Multi-page plan records:** a multi-page upload creates one plan record per page
  (`plan.page` = source page) but annotations are plan-local — always `page: 1`
  (precedent: A0.1(2), S0.0(2..7), A0.0(4) all render with page:1). `updatePlan`
  return selections need `readPlan` (blocked) — send mutations with EMPTY selection `{}`;
  several updatePlan mutations batch fine in one query via `_` aliases.
- **Giant-save discipline held:** 107.9K-char full-replace (100 params) worked first try
  using the run-(4) recipe — payload file → 6 printed chunks → bare-turn updateJob with
  `job{id}` selection → separate read-back parsed from the persisted tool-result file.
- **State after run: 100 parameters** (GF 10, FF 9, openings 8, SF 10, Roof 7, structural
  30, MEP 16, M/P completion 10). Open RFIs: WH gas vs electric; slab 6″/8″ note; grid-9
  GB1/GB2 tag; 03.10-vs-06.25 A2.0/M/P version confirmations. Cost-item wiring still the
  open next capability.

### 2026-07-04 (4) — Job 2025-227 — MEP E1–E3/M1/P1 (06.25 set) — Claude
- **Scope:** 16 MEP parameters (7 E, 6 M, 3 P) → job total 90; 5 plan pages calibrated
  (all true ¼″, k=18 — verified on the deck envelope 721 pt / 40′).
- **MEP counting toolkit:** device labels that ARE real text anchor exact counts (GFCI ×13,
  CU-1/2/3, EF-3, WH, CHARGE) — extract positions and mark them verbatim. Symbols with
  outlined text (SD/CO, switch letters, diffuser CFM tags) need the montage-classify
  pipeline: circle-radius classes separate recessed cans (12pt (R)) from vanity stems
  (9pt), exhaust hubs (21pt), grid bubbles (24pt); furniture/cloud curves pollute 18pt+.
  Letter glyphs strike again: none this round, but margin LABELS vs equipment SYMBOLS did
  — text-extracted CU/AHU positions were the leader notes, not the units; always re-anchor
  markers to the drawn equipment on the overlay pass.
- **Panel schedules are the electrical truth:** E3.0 gave 400A service, 2×200A panels,
  EV ×2 (12.3 KVA), AHU×3 + CU×3 circuits, demand calc — count-anchored these even where
  plan symbols were ambiguous. Read schedules BEFORE counting symbols.
- **Set-completeness check per discipline:** M and P sheets cover GF+FF only — SF + roof
  distribution (3 baths, roof PWDR, outdoor kitchen/shower, AHU-2/3 ductwork) is missing
  from the permit set → headline RFI. An MEP takeoff that doesn't state what the set
  DOESN'T cover understates scope by whole floors.
- **API/harness lessons:** point-marker styling (fillColor/strokeColor/strokeWidth) is
  OPTIONAL — measurement `color` drives display; stripping it cut the 90-param payload
  27%. Full-replace saves at this scale exceed a single response budget if anything else
  shares the turn: generate the payload to a file, print it in chunks for verbatim copy,
  then send the updateJob as the ONLY output of its turn with a minimal selection
  (`job{id}`), and verify via a separate read query parsed from the persisted result file.
- **State after run: 90 parameters** (GF 10, FF 9, openings 8, SF 10, Roof 7, structural
  30, MEP 16), 13 plan pages calibrated. Cost-item wiring still the open next capability.

### 2026-07-04 (3) — Job 2025-227 — STRUCTURAL S1.0–S6.0 (04.10 S0.0 set) — Claude
- **Scope:** full structural takeoff → 30 parameters across 6 plan pages (foundation, GF
  columns/walls, FF/SF floor structure, roof deck, top canopy). Job now carries 74 params.
- **Mixed plot factors in ONE file:** S1.0 & S4.0 at k=17.0 (94.4%), S2.0/S3.0/S5.0/S6.0 at
  k=18.0 (true ¼″). Measure EVERY page — never carry a sheet's k to its neighbor.
- **Dashed-symbol detection:** pile circles = ~16 tiny 2-3-segment dashes each → union-find
  cluster on dash centers (6pt radius), filter 10–20pt square bboxes. 61 found + 5 verified
  under labels/junctions via spacing-gap analysis (median ~6′-4″ oc; gap ≈ 2× median ⇒
  hidden pile — confirm each with a zoom montage before adding). **9 false positives were
  letter glyphs (O in OVER, e in TERMITE)** — montage-verify every candidate class.
- **Outlined tag reading at scale:** hexagon GB tags & column marks don't text-extract —
  batch-crop ALL instances into one PIL montage and read once (38 tags in one image).
- **Fill-fragment merging:** solid column symbols split into fill bands around white rebar
  dots — merge dark fills within 5pt to blobs; C-3 = ~24pt blob, C-1 = ~9pt dotted square
  (multi-frag + density>0.5 separates them from dim ticks). One C-3 evaded the vector merge
  and was caught only on the overlay — always ring-and-count on the sheet.
- **Cross-discipline reconciliation caught the big ones:** (a) S-set shows GF front
  wall/foundation at 59′-8″ + 5′-0″ drive-under apron to the 64′-8″ column line (SW corner
  column on a beam stub) — resolves the A-vs-S "conflict" as a porte-cochère front, RFI'd
  for door-line confirmation; (b) S3/S4 north+south strips are CONCRETE balcony decks
  (#5@12 mat EW) not wood trusses — S4's three decks sum 406.8 SF vs A2.0 balconies
  406.7 SF (independent reproduction!); (c) S6 canopy = exactly the A2.0 covered zone
  (20′ × 43′-7″, 4 bays @ 10′-11″).
- **Document conflicts RFI'd, priced conservative:** note 4 "FLOOR SLAB TO BE EIGHT (6)
  INCHES" vs plan labels 6″ (±15 CY); grid-9-west grade beam tagged BOTH GB1 (above, std
  convention) and GB2 (below) — priced as heavier GB2.
- **API nits:** plain `linear` measurements REJECT `unit` (only linearArea/areaVolume/
  linearVolume take it); large updateJob echoes get persisted to a tool-result file —
  parse it programmatically for the read-back diff instead of re-reading inline.
- **State after run: 74 parameters**, 8 plan pages calibrated. Cost-item wiring still open.

### 2026-07-04 (2) — Job 2025-227 — SF + Roof (A2.0, 04.10 A0.0 set) — Claude
- **Off-scale plot detected & calibrated (§4.1 guard validated):** the A2.0 sheet plotted at
  **94.4%** of nominal ¼″ — apparent 40′ spans measured 680 pt, not 720. Solved
  **k = 17.00 pt/ft** by least-squares on consecutive dimension-text center spacings
  (6 estimates within ±0.03), → `scale = 17.0 × 3.28084 = 55.77427821522309` pt/m.
  Verified against 40′-0″ (680.0 pt) and 64′-8″ (1,099.2 pt) printed overalls exactly.
  **Never assume the §1 nominal table — measure a known dim first, every sheet.**
- **Plans queries paginate:** a size-25 default hid existing page records → created a
  duplicate plan for page 4 (deleted via `deletePlan`). Query `plans` with `size:40`+ and
  check for the page BEFORE `createPlan` — the whole file is usually already imported.
- **Elevations killed 5 phantom windows:** first pass placed 12 SF window markers; the
  four elevations + 300-DPI wall strips proved 7 openings (2 W, 3 E, ribbon S, 1 in SE
  balcony back wall) — the north-face "windows" were the balcony door-M assemblies' own
  glazing. Two-source rule (§4.4) is the difference between 12 and 7.
- **Congested-core guard paid again:** roof bulkhead first drawn as a rectangle (202 SF);
  300-DPI zoom showed a **T-shape incl. the door-J vestibule** → 8-pt polygon, 221.7 SF,
  reconciling the printed tab's 220. Multi-point polygons work fine as `isNegative` too
  (bulkhead subtracted from covered zone as an 8-pt negative path).
- **API nit:** `area`-type parameters REQUIRE non-null `unit` ("foot") — count types don't.
  Error surfaces as `A non-null value is required at ...parameters.N.unit`.
- **Cross-checks vs printed roof tabulation:** open 1,606 (tab 1,650), covered-net 650
  (tab 723 — different zone splits; tab's open+covered+bulkhead sums to the gross deck),
  bulkhead 221.7 (tab 220 ✓). Differences stated in measurement names.
- **Version-mismatch RFI raised:** SF/Roof measured on the 04.10 A0.0 set; GF/FF basis is
  the 06.25 A0.1 permit set — confirm no A2.0 revision between sets.
- **State after run: 44 parameters** on the job (10 GF + 9 FF + 8 openings + 10 SF + 7 Roof),
  both plan pages calibrated, one note per page. Full-replace merge preserved all 27.

### 2026-07-04 — Job 2025-227 (655 115th Ave, Treasure Island) — GF+FF+openings — Claude
- **Discovered/verified:** everything in §1 (first run; coordinate space, scale=pt/m,
  recompute-from-geometry, isNegative, full-replace).
- **Caught by overlay-verify:** foyer diagonal face-mixing; recessed front balcony;
  elevator box 11′ off. Zero errors reached JobTread uncorrected except the foyer
  polyline (fixed in the next save; app-recomputed value exposed the jog).
- **User-confirmed in UI:** 2,586.67 SF / 40′ / 4 displayed exactly as computed.
- **Process changes adopted:** compose param JSON programmatically (unique-id check);
  values advisory; ± tolerances into names; one text note per plan.
- **Open for next run:** cost-item wiring; SF/roof pass; cdn.jobtread.com allowlist
  request pending; door/window schedule still absent from design set (± on counts).
