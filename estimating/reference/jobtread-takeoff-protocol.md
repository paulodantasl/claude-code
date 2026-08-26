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
| Scale for imperial drawings | `scale = inches_per_foot × 3.28084 × 72` → **¼″=1′-0″ → 59.05511811; ⅛″ → 29.5275591; 3/16″ → 44.2913386; ½″ → 118.1102362; ⅜″ → 88.5826772; 1″ → 236.2204724** | All recurring org values matched; 40′-0″ printed dim measured exactly 720 pt on a true-scale ¼″ sheet |
| Values are **recomputed from geometry** | The `value` you send is advisory; JobTread recomputes from annotations × **current** plan scale. Recalibrating a plan silently updates every value measured on it (feature: the takeoff self-corrects) — so printed values in notes can drift from live values | Sent 96.22 LF hand-sum; read back 96.825; A2.0 user recalibration (Δ0.004%) shifted all its param values on the next read |
| **Derived-value semantics by type** | `area`→SF, `linear`→LF, `count`→n markers, `linearArea`→**SF** (length×depth), `areaVolume`→**ft³** (area×depth), `linearVolume`→**ft³** (length×width×depth). Send LF/SF if you like — the server stores the derived total. Cost formulas on volume params get ft³: **divide by 27 for CY** | 2026-07-10 audit: all 139 measurements re-derived at 0.000% deviation only after applying these semantics (ratios exactly = depth, w×d) |
| `isNegative` subtraction | Closed path with `isNegative: true` inside a measurement subtracts exactly | GF net area read back = interior − patio − core to full precision |
| **Full-replace semantics** | `updateJob.parameters` and `updatePlan.annotations` REPLACE the whole array | Read-backs always mirror exactly what was last sent |
| Where geometry belongs | **Parameter measurements embed their own annotations** (+ `planId`, `color`); `plan.annotations` = free markup only (meta + notes). Don't duplicate shapes in both — they'd render twice | UI-created takeoff (632 Boca Ciega) + our own saves |
| Parameter types | `area, linear, count, linearArea(depth), areaVolume(depth), linearVolume(width+depth), areaPitch, linearPitch(pitchX/Y), linearDrop(startDrop/endDrop), formula(name+formula), number, option` | Schema introspection `parameters` type |
| Path structure | `path.points` = array of `{annotationId}` refs to sibling `point` annotations; `isClosed` for areas; for a **perimeter as linear**, use an open path with N+1 points (repeat the first coordinate as a new point id) | Org example + our saves |
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
  the environment's network settings.
- Workaround: pull the **identical file from Google Drive** (teams store the same PDFs).
  Match by exact filename. Drive MCP downloads ≳8 MB may fail ("session expired") — prefer
  the smaller per-discipline files.
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
| 11 | Composed params from a CSV by `LIKE '%…%'` → silently matched the wrong rows | Constrain by division AND unit; `assert len(matches)==1` and let it fail loudly |
| 12 | Dimension lines masquerade as walls (a 42.7 ft "partition") | Require the parallel face PAIR (≈5.6 pt for a 4-7/8" stud wall); a lone long line is a dimension or leader |
| 13 | A printed dimension spans MORE than the room it labels | Bound the dimension against the wall faces it actually terminates on before using it |
| 14 | A clean continuous chain is not evidence it is the right line (traced the canopy, not the storefront) | Overlay-verify POLYLINES too, not just polygons; both ends must close on verified wall faces |
| 15 | A correct TOTAL hid a wrong SPLIT (block divided at a wall that is outside the block) | Verify the DIVIDER against a face pair whose overlap spans the block; never extend a wall line in from outside |
| 16 | "Matches the printed dimension exactly" *was* the error — the printed chain runs face-to-far-face | Decide the wall reference once (room-side face); classify every edge against its pair, not against the printed dim |
| 17 | The font-size discriminator cuts BOTH ways — over-count (legend key at 12.57 pt) and under-count (device filter excluded 6.17 pt) | Histogram tags by font size, then RENDER A SAMPLE OF EVERY BAND before deciding which bands are devices |
| 18 | A scaled plan with no measurements looked "done" because it still carried its upload filename | Diff the set of scaled plans against the set of plans carrying geometry; query `plans` with `size: 60` |
| 19 | Called a stated area "8.1% HIGH" and published it — it was a different reference, not an error | Before declaring any stated quantity wrong, RE-DERIVE it on its own convention. A0's 2,797 SF reproduces to 0.08% by offsetting the traced rooms to wall centrelines |
| 20 | A plan-wide assumption ("the floor is LVT") survived because no one opened the room finish SCHEDULE | Read the schedule, not just the plan graphic. 5 of 26 rooms were CONC or VCT; the LVT line said "net room area" and had never been netted |
| 21 | A vendor sheet is drawn to scale AND stamped "NOT FOR CONSTRUCTION" | Leave it unscaled, like an NTS sheet. A scale invites measuring off a drawing its own author has disclaimed — mine its SCHEDULE instead |
| 22 | A column-position parse of a spec schedule dropped 8 rows and manufactured 3 false "uncosted" items | Reconcile a parse against its own row count before reporting a gap, then READ the schedule. All three were correctly not separate scope |
| 23 | Four SPECIFICATION sheets were never opened — the estimate cited MEP5 13x, MEP6 19x and MEP1-MEP4 ZERO times, hiding $15,570 of required scope | Count citations PER SHEET across the whole estimate. A sheet with zero citations has not been read. Verifying what is DRAWN is not verifying what is REQUIRED |
| 24 | "Implied and not scoped" was recorded for work that had a dedicated full spec section (MEP4 = 260573, an entire sheet) | "Implied" is a claim to verify, not a conclusion. Before inferring scope from a schedule note, go find the section that mandates it |
| 25 | Raised an RFI for a "missing" sheet SED.3 — every detail it supposedly held was on SED.2, and 14 of OUR OWN citations pointed at the wrong sheet | Resolve the reference before raising the RFI. A citation to a sheet not in the set is evidence of a bad citation at least as often as evidence of a missing document |
| 26 | A volunteered alternate carried a **$500 engineer review fee printed on the same sheet as the fixture schedule**, turning a published $572 deduct into $72 | A drawing sets COMMERCIAL terms as well as technical ones. Read substitution, alternate and bid-form notes as priced scope — a fee that attaches to something you volunteered is a cost you chose |
| 27 | A withdrawn finding ("A0 is 8.1% high") was corrected in the narrative but left standing, as fact, in two line-item basis notes | A retraction is not complete until every DERIVED copy is gone. Grep the withdrawn claim across every deliverable, not just the document that argued it |
| 28 | A published cost-by-division table still summed to a 262-row, $806,101 state three revisions later — 9 of 19 divisions wrong — while its OWN arithmetic stayed perfect | A stale table that is internally consistent is harder to spot than a broken one: every check inside it passes. REGENERATE derived tables from the source; never patch them |
| 29 | "Exhaust fans integral" treated a factory INTEGRAL DISCONNECT as satisfying a required wall CONTROL switch — two devices, two locations | When a schedule note and a plan keynote both name a device, they are naming a device. Reconcile keynotes per sheet the way you reconcile schedules |

## 7. What good looks like (reference result)

Job 2025-227, one A1.0 sheet (GF+FF at ¼″): **27 parameters** — footprint/plate 2,586.67 SF
each; perimeter 209.33 LF (walls 2,721.3 / 2,512.0 SF @ 13′/12′); patio 360.9; balconies
196.7 + 143.3 (recessed); nets 1,943.6 / 2,156.3 via isNegative; cores 144.4 / 120.5;
partitions 96.8 / 130.0 LF; vents ×8; full openings schedule (2 OH + entry + 2 sliders +
5 GF windows + 3 GF interior; 5 balcony doors + 7 FF window units + 9 FF interior doors) —
all geometry-anchored, cross-floor reconciled (both floors sum to the same 2,448.9 SF
interior; cores and patio/balcony walls stack at identical coordinates).

## 8. Next capabilities (not yet built — pick up here)

- **Cost items wired to parameters** (`createCostItem` + quantity formulas referencing
  parameter names) — the estimate then updates when a measurement changes.
- Per-room breakdowns; `areaVolume` for slabs (depth-verified), `linearArea` for wall
  areas by height zone. (GF+FF+SF+Roof passes complete — see Run Log.)
- Batch calibration of every plan page in a job (scale table §1 makes this mechanical).
- Elevations-page markers (bind the same parameter to multiple planIds — one measurement
  per plan page).

## 9. RUN LOG (append one entry per run — this is the improvement loop)

### 2026-08-24 — Job 2026-374 (Advantage Dental+, Wesley Chapel) — PERMIT-SET PARAMETER WRITE — Claude
- **Scope:** full `/bid-commercial` pipeline off the 10-Aug-2026 A/S/MEP permit set (31 sheets) + 7-sheet Henry Schein dental set, then **56 measured parameters written** to Job 2026-374. Supersedes the 14-Jul test-fit run: that job's parameters read back **`null`** — the 44 number-params from the test fit are gone, so the permit-set upload replaced them. **Read before you merge: "read-merge-write" assumed a non-empty array and would have silently written nothing to merge.**
- **The Pave MCP WAS available this session and I nearly missed it.** A ToolSearch for `"jobtread pave takeoff job parameters"` returned nothing; `"jobtread pave plans annotations measurements calibration"` surfaced `mcp__Ideal__query` immediately. **Search on the API's own vocabulary (plans/annotations/calibration), not on the task vocabulary (takeoff/parameters)** — and never conclude "no JobTread this session" from one miss. I told a subagent it was unavailable; that was wrong.
- **⚠ SUPERSEDED — see the 2026-08-25 entry: this bullet is WRONG. `measurements: []` silently DISCARDS the value.** Typed measurement params work WITHOUT geometry — new, and better than bare `number`.** Validation walks one field at a time: `{name, measurementType, value}` → *"non-null required at .measurements"* → add `measurements: []` → **accepted, value holds on read-back**. A *manual* measurement additionally demands `color` (and takes `planId`, `annotations: []`). So there are three working shapes, in increasing order of fidelity: bare `number` `{name,value}`; **typed + empty `measurements: []`** (carries `measurementType` + `unit`, reads as a real takeoff parameter, value stands because there is no geometry to recompute from); and typed + geometry-anchored measurements. **Prefer the middle shape for value-only takeoffs** — §5's unit-in-the-name workaround is no longer needed, the unit is a real field.
- **Independent scale confirmation, worth doing every time.** The takeoff was measured off the PDF vector layer at **13.5 pt/ft** before JobTread was ever queried. The plans already in the Plans tab carry `scale: 44.29133858267717` on A1/A2/A6 — and 0.1875 in/ft × 3.28084 × 72 = 44.2913386, i.e. **exactly 13.5 pt/ft (3/16″ = 1′-0″)**. Two independent derivations agreeing is a free cross-check on the whole takeoff; A0 sits at 29.5275591 (⅛″), so **scale varies per sheet within one set — never assume one scale for a job.**
- **Byte-identical file match is checkable and worth checking.** `job.plans.nodes.file.size` returned **25,031,656** for the ASMEP set and **1,858,489** for the Henry Schein set — both exact matches to the local uploads. Confirms the geometry measured locally belongs to the same file the Plans tab renders, without touching the blocked CDN.
- **Sheet-name → planId map is the useful artifact** (7 ASMEP pages calibrated, 3 Henry Schein pages at `scale: null` — uncalibrated): A0 p1 ⅛″, A1 p2, A2 p3, A6 p7, M1 p17, P1 p20, MEP6 p16, all 3/16″.
- **Guard #11 (new): assert on ambiguous substring matches when composing params from a CSV.** Building the payload by `item LIKE '%...%'` silently matched the wrong rows twice — "Core drilling" hit a **Div 01 after-hours ALLOW row (1)** instead of the **Div 03 quantity (12)**, and "Branch circuits" double-counted the lighting rows (83 vs the true 81). Both were caught only because the builder asserted `len(matches)==1`. **Constrain by division AND unit, and let the assertion fail loudly rather than defaulting to the first hit.**
- **State after run: 57 parameters** (17 area, 16 linear, 24 count) spanning divisions 00/02/03/06/07/08/09/10/12/21/22/23/26/27/28, each name carrying its basis, tolerance or open RFI. **2 are geometry-anchored on A1** (see the geometry addendum below); 55 remain value-only. **Open next:** geometry for the remaining value-only params, and cost-item wiring (`createCostItem` + quantity formulas referencing these parameter names).

### 2026-08-24 (b) — Job 2026-374 — GEOMETRY-ANCHORED ADDENDUM (the same run, second pass) — Claude
- **Why:** the first pass wrote *values*, not measurements. Typed params with `measurements: []` carry a unit and read as takeoff parameters, but **nothing is drawn on the sheet** — in JobTread's vocabulary they are not measurements. When the ask is "measurements in the Plans tab," value-only is under-delivering. Corrected in this pass for the 7 operatories.
- **⚠ COORDINATE SPACE — the one that will bite you. `get_drawings()` returns UNROTATED MediaBox coordinates; JobTread uses the RENDERED page.** These pages are MediaBox 1728×2592 portrait with `/Rotate 270`, displayed 2592×1728 landscape. The reference plan's stored `meta` reads `width: 2592, height: 1728, rotation: 0` — i.e. **JobTread stores the rendered size with rotation 0, not the MediaBox with rotation 270.** Transform every extracted point with `page.rotation_matrix` before writing: here `rendered = (my, 1728 − mx)`. Skip it and every annotation lands off-page or 90° out. Verify by mapping the four MediaBox corners and confirming they hit (0,0)…(2592,1728) exactly.
- **`isManual: false` is REJECTED** — *"Expected false … to be true"*. It is a constant-`true` marker for hand-entered measurements. **Omit `isManual` entirely on geometry-anchored measurements**; include it only (as `true`) for a manual value, where `color` then also becomes required.
- **`updateJob.job.parameters` takes no subfield selection** — `parameters` is a scalar JSON blob. `{"parameters": {"name": {}}}` fails with *"The field \"name\" … is not expected"*. Select `{}` or pick a different root field (`id`/`name`) to keep the response small on a 15 KB write.
- **Guard #12 (new): dimension lines masquerade as walls.** Three of the longest horizontal runs on A1 (42.7 ft, spanning x 551→1127) were **dimension lines, not partitions** — banding on them put Exam 123 at 7.47 ft against its printed 10'-5". The overlay-verify pass (§4 step 6) caught it immediately. **Filter candidate walls by looking for the parallel face PAIR** (here 5.6 pt ≈ 4-7/8"); a lone long line with no partner is almost always a dimension or leader line.
- **Scale confirmed three independent ways**, which is worth doing before trusting any traced area: (1) local vector measurement = 13.5 pt/ft; (2) JobTread's stored `scale` 44.29133858 pt/m ÷ 3.28084 ÷ 72 = 13.5 pt/ft; (3) **dimension-chain closure** — printed room dims read 10'-5" while the clear face-to-face measures 134.9 pt = 9.99 ft, the difference being exactly one 4-7/8" partition, i.e. the printed dims are centerline. Cross-check the resulting area both ways: 214.6 × 134.9 pt = 158.8 SF at 13.5 pt/ft, and 158.85 SF via JobTread's pt-per-metre scale — **0.03% apart**.
- **Geometry lives in the parameter, not on the plan.** After writing 7 area polygons + 7 count markers, `plan.annotations` still reads `[]` — correct per §1. `plan.annotations` carries only `meta` + the summary `text` note; the shapes ride inside `parameter.measurements[].annotations` with `planId` + `color`. Writing both would render the shapes twice.
- **Result: 7 operatory rooms drawn wall-to-wall on the A1 Dimension Plan** (NOT the RCP — A1 carries both, offset ~1147 pt, so *always* confirm which half you are tracing): Hygiene Flex 116 / 113 / 111 at 158.8 SF each, Exam 120 / 121 / 123 / 124 at 154.7 SF each, **1,095 SF total**, plus 7 count markers at the chair positions. Four y-bands of exactly 134.9 pt each — that regularity is itself a check.


### 2026-08-25 — Job 2026-374 — GEOMETRY COMPLETION + WRITE-SHAPE CORRECTION — Claude
- **⚠ CORRECTION to the 2026-08-24 entry: `measurements: []` does NOT hold a value.** That entry
  claimed typed params with an empty `measurements` array "read back with the value standing." They
  do not. Read-back of the 57-param write showed **56 of them with `measurementType` + `unit` present
  and the `value` key ABSENT** — the server computes a typed parameter's value from its measurements,
  so an empty array computes to nothing and the supplied number is silently discarded. The write
  succeeds, the panel shows a unit and no quantity, and nothing errors. **Always read back and assert
  `'value' in param`, not just that the mutation returned 200.**
- **There is NO value-only measurement shape.** Walking the validator one field at a time:
  `measurements[0]` requires `name` → `value` → **`color`** → **`annotations`** (non-null). Since
  `annotations` is mandatory, a measurement cannot exist without geometry. So the three "shapes" in
  the prior entry collapse to **two**: bare `{name, value}` (no `measurementType`, no `unit` — the
  value stands), and typed + genuinely geometry-anchored. **§5's unit-in-the-name convention is NOT
  obsolete — it is the only way to carry a unit on a value-only quantity.** Reinstated here: 52
  value-only params were rewritten as `{name: "... = 2,797 SF", value: 2797}`.
- **`updateJob` is a ROOT mutation, not a field on `job`.** `{"job": {"$": {"id"}, "updateJob": …}}`
  fails with *"The field \"updateJob\" does not exist at \"job\""*. Correct form:
  `{"updateJob": {"$": {"id": …, "parameters": […]}, "job": {"$": {"id": …}, "id": {}}}}` — note the
  output `job` needs **its own `$: {id}`**, since it is a lookup, not a back-reference.
- **`isClosed: false` is REJECTED — same constant-true class as `isManual`.** *"Expected false … to
  be true"*. **Omit `isClosed` entirely for an open polyline;** include it as `true` only for closed
  areas. This is how you draw a `linear` measurement (a polyline path) versus an `area` one.
- **Validate the envelope with a no-op before sending a 30 KB payload.** Three shape errors cost three
  full re-sends of the whole parameter array (full-replace means you cannot probe with a subset without
  destroying the rest). `{"updateJob": {"$": {"id": …, "name": "<current name>"}, …}}` is a free
  round-trip that proves the envelope. Do that first, every time.
- **`readPlan` can be denied at root while plans stay readable through the job.** `{"plan": {"$": {"id"}}}`
  returned *"requires the readPlan action"*, but `{"job": {"$": {"id"}, "plans": {"nodes": {…}}}}`
  returned everything including `annotations`. Same for mutations: `updatePlan` works, but selecting
  `plan` in its output trips the same grant check — **select nothing** (`{"updatePlan": {"$": {…}}}`
  returns `{}` on success) and verify via the job path.
- **Open polylines let you measure a curved wall exactly.** The storefront is drawn as a **faceted
  chord chain, not a bezier** — 6 straight segments, 7 vertices, filtered out of `get_drawings()` by
  taking long NON-axis-aligned lines in the region. 45.14 LF. Hunting for curve items first wasted a
  pass: 4,935 bezier segments in that region were all 31.5 pt annotation-bubble circles.
- **Guard #13 (new): a printed dimension may span MORE than the room it sits in.** Corridor 106's
  vertical "18'-9 1/2"" reads like the room's depth; the room is 14.6 ft. The dimension is a **chain
  running from Corridor 109's far wall (y 674.5) through to y 928.3** = 18.800 ft vs printed 18.792.
  Same sheet, "6'-5 1/2"" spans x 543.0→630.2 = 6.459 vs printed 6.458 — **centerline-to-centerline,
  so the clear width is one 5.5 pt wall less (81.7 pt)**. Test a dimension against *chains* of walls,
  not just the nearest pair, before concluding your trace is wrong.
- **Grey out what is already drawn to find what is not.** Rendering the 21 finished rooms as filled
  rects over the sheet made the remaining white spaces — and their labels — unmistakable in one look.
  This is the same overlay-verify pass as §4 step 6, used for coverage instead of correctness; it is
  how the corridor-inside-operatory error was caught, and how Corridor 106 / Admin Storage 102 were
  found still open.
- **Result: 63 parameters, 11 geometry-anchored, 194 annotations, 23 rooms drawn wall-to-wall**
  (1,918.4 SF of A0's 2,797 SF, 69%), plus 45.1 LF storefront + 54.5 LF east wall as open polylines,
  and trade-device markers on P1 (18 plumbing fixtures) and M1 (23 supply / 15 return / 3 exhaust).
  `meta` added to P1 and M1 — **without it a plan's markers have no page frame to position against.**
- **Stopping point, stated honestly:** Waiting 100 / Admin 101 / Break 125 are NOT drawn and should
  not be. Their mutual boundaries are a reception counter and casework, not walls, and their south
  edge is the storefront curve — any three-way split would be an invention. The area basis is itself
  an open RFI (A0 2,797 vs lease 2,544 SF). **When the remaining geometry needs a decision rather than
  a measurement, write nothing and say so.**


### 2026-08-25 (b) — Job 2026-374 — WITHDRAWN A PUBLISHED TRACE (Guard #14) — Claude
- **What happened:** the 45.1 LF "curved storefront" written earlier that same day was **the wrong line**, and it
  had already been published to the job. It followed the **canopy / sidewalk edge**, not the demising glass.
- **Guard #14 (new): a clean continuous chain is not evidence it is the right line — bound it against a known
  interior face.** The tell was decisive and took one check: the chain's west end sits at **x = 400.4**, while the
  west exterior wall's own verified face pair is **415.9 / 423.7**. A tenant boundary cannot run outside the
  building's exterior wall. **Before writing any traced perimeter, assert every vertex falls inside the envelope
  established by the wall pairs you already trust.** That single assertion would have caught this before the write.
- **Why the chain-walker preferred the wrong line:** an endpoint-snapping longest-path walk over the region returned
  the canopy edge (8 nodes, 579 pt) because it is drawn as **one uninterrupted polyline**. The real storefront is
  **broken into panels by mullions**, so no single connected chain spans it. **Continuity selects for the simplest
  line in the region, which is often an outline, a canopy, or a curb — not the enclosure.** Rank candidates by
  whether they terminate on known wall faces, not by length.
- **Distinguishing glass from wall in the same run:** the glazing panels carry a **~1.1 pt twin** (the two faces of
  the glass at 13.5 pt/ft); solid piers in the same run carry the **~5.5 pt** partition twin. A single line with no
  twin at either spacing is not part of the enclosure. This storefront alternates glazing and pier, so no one
  spacing filter finds the whole boundary.
- **⚠ SUPERSEDED by the 2026-08-26 entry — the front of house WAS traceable and the RFI WAS closable by measurement. The bullet below over-applied a good instinct.** Where the trace ends and the RFI begins — and how to tell the difference.** The three front-of-house spaces
  (Waiting 100 / Admin 101 / Break 125) resolve to a residual of **626–879 SF** depending on whether A0's 2,797 SF
  or the lease's 2,544 SF governs. **The entire 253 SF discrepancy lands inside that one space — 34% of it** — while
  every traced room closes to ~0.05%. A polygon carrying a 34% band is not a measurement. **When the unresolved
  spread is a large fraction of the space you are about to draw, the deliverable is the residual and the RFI, not
  the polygon.** Recorded as a value-only parameter naming both bases so the number cannot be mistaken for measured.
- **Process note:** the error surfaced only because the user pushed back on a "finished" claim. The overlay-verify
  pass (§4 step 6) had been run on the rooms but **never on the perimeter trace** — it was written from extracted
  segment coordinates without being rendered back over the sheet. **Overlay-verify every geometry write, including
  linear ones.** Areas got the check; the polyline did not, and that is exactly where the defect was.
- **State after run: 64 parameters, 11 geometry-anchored** — 23 rooms wall-to-wall (1,918.4 SF), east exterior wall
  54.5 LF, trade markers on P1 and M1. South perimeter withdrawn pending a correct glazing trace.


### 2026-08-26 — Job 2026-374 — TAKEOFF COMPLETED; THE MEASUREMENT CLOSED THE RFI — Claude
- **⚠ CORRECTS the 2026-08-25 (b) entry.** That entry argued the three front-of-house spaces should NOT be traced,
  because the A0-vs-lease spread was 34% of the residual. **That reasoning conflated two different things.** A traced
  polygon measures **the drawing**; the RFI is about **which stated basis is correct**. Measuring the drawing does not
  require the RFI to be settled — and here it *settled* it. **When sources disagree about an area, measuring is the way
  to adjudicate, not a thing to postpone until they agree.**
- **Result: the whole suite is now traced wall-to-wall.** 23 rooms 1,918.4 SF + front of house 675.1 SF (one 38-vertex
  polygon; Waiting/Admin/Break are divided only by casework, so one polygon is the honest unit) = **2,593.5 SF total**.
  Against the two stated figures: **lease 2,544 SF → +1.9%** (ordinary usable-vs-rentable), **A0 code summary 2,797 SF
  → −7.3%**. The lease is corroborated; A0 is materially high. Three line items had been priced on 2,797 (final
  cleaning, selective demolition, sprinkler) = **~$1,475 direct** overstated.
- **How the correct storefront line was finally isolated, after Guard #14 killed the first attempt.** Not by chaining —
  chaining is what picked the canopy. By **spacing signature, per panel**: glazing carries a ~1.1 pt twin (glass faces
  at 13.5 pt/ft), solid piers carry the ~5.5 pt partition twin, and single lines with neither twin are canopy, curb or
  furniture. The run alternates glass and pier, so **assemble panel by panel and let the twin spacing classify each
  one**, rather than looking for one filter that spans the whole face.
- **The closure test is the acceptance criterion, and it is cheap.** The accepted chain starts at (435, 1197) — where
  the west exterior wall's verified face 423.7 terminates at y=1191.6 — and ends at (1089.5, 1007.2), on the east wall's
  verified inner face 1090.4. **Both ends landing on independently verified wall faces is what promotes a candidate
  from plausible to correct.** The withdrawn canopy chain failed exactly this test at its west end (x=400.4).
- **Overlay-verify caught the difference in one image.** Drawing all three candidates in different colours over the
  sheet — accepted enclosure, the 7-ft parallel pair, the canopy — showed instantly that the middle candidate ran
  *inside a bench* and the canopy ran *outside the building*. **Render competing candidates together; the wrong one is
  obvious in a way no coordinate listing makes obvious.**
- **Non-convex is fine.** The front-of-house polygon includes a V-notch where the entry vestibule projects. Shoelace
  handles it; JobTread renders and stores it without complaint. Do not simplify a notch away to keep a polygon convex —
  the notch was ~30 SF here.
- **State after run: 13 geometry-anchored parameters, every named space on the sheet measured.** No space on A1 is now
  un-traced. The only remaining open item is unrelated: E1 is not uploaded to JobTread, so the electrical counts stay
  value-only, and that is where the +1 junction-box discrepancy sits (takeoff 31 vs 32 tags).


### 2026-08-26 (b) — Job 2026-374 — DELAYED RECOMPUTE: an immediate read-back cannot verify geometry — Claude
- **Corrects a conclusion drawn earlier in this run.** After a geometry write I read the job straight back, saw my own
  rounded number echoed (`79.67` for Corridor 106), and concluded JobTread *stores* what you send rather than
  recomputing. **Wrong.** A read six hours later returns `79.6703978052126`. The server DOES recompute from geometry ×
  plan scale — **the recomputed value simply is not there yet on an immediate read.**
- **Consequence for the protocol: an immediate read-back is NOT a verification of a geometry-anchored measurement.**
  It only proves the write was accepted. It cannot distinguish a correct polygon from a wrong one, because at that
  moment the value on the server is still the number you supplied. Verify geometry by **overlay against the sheet**
  (§4 step 6), and treat a later read as the arithmetic cross-check.
- **That later read is worth waiting for, because it is a genuinely independent check.** JobTread's own engine,
  using the stored scale 44.29133858, reproduced every value computed locally by shoelace / chain length:
  front of house 675.080301783266, enclosure run 73.6204858317247 LF, east wall 54.4592592592593 LF,
  Corridor 106 79.6703978052126, Admin Storage 102 53.9390946502056. **Agreement to 12 significant figures on a
  38-vertex non-convex polygon confirms the coordinate transform, the scale and the shoelace all at once** — a
  free third-party audit of the whole geometry pipeline, available on any run, for the cost of one delayed read.
- **Round only when you speak, never when you write.** Values sent rounded (675.1, 73.62) come back at full precision
  once recomputed, so the rounding is discarded anyway — but summing *rounded* room values is what produced the
  published total of 2,593.5 SF against a true 2,593.41 SF. Harmless here (0.09 SF), but sum the stored precise
  values when a total is the deliverable.
- **State: verified.** 23 rooms + front of house = 2,593.41 SF measured; lease 2,544 SF corroborated at +1.9%,
  A0's 2,797 SF confirmed 7.3% high. A coverage sweep (every traced polygon overlaid on A1) found no un-traced space;
  the duplicate "Lab 112" text in Corridor 122 is a leader label, not a missed room. E1 is still not uploaded, so the
  electrical counts remain value-only and the +1 junction-box discrepancy stays open.


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

### 2026-08-26 (c) — Job 2026-374 — THE LAST TWO TRADE SHEETS, AND WHAT THEY EXPOSED ON THE FIRST ONE — Claude

Ran the plan list at `size: 60` (45 plans) and found **two scaled sheets still untraced**: `FP1 —
Floor 1 Fire Protection` (uploaded but never renamed off the generic filename, so it read as
"…ASMEP.pdf (25)") and `MEP6 — Floor 1 MEP Demolition`. Tracing them changed the takeoff more than
the trades themselves did.

- **A sheet can be finished and still be invisible.** FP1 was already scaled correctly and sitting
  in the plan list under its upload filename. Nothing about the plan list said "untraced trade."
  **Enumerate scaled plans and diff them against the set of plans that carry measurements** — a plan
  with a scale and no geometry is an unfinished sheet, whatever it is called.

- **Read the legend before you count anything.** FP1 has no head symbols at all. Its note directs the
  contractor to *"reconfigure existing base building fire sprinkler layout… per NFPA 13"* — a
  **performance specification**. The countable thing on the sheet is not heads, it is the **hazard
  classification**, drawn as three hatches. Discriminator, measured off the legend swatches: **45° =
  Light Hazard, 135° = Ordinary Hazard Gp 1, both = Ordinary Hazard Gp 2**, all at 9.0 pt spacing.
  Sampling diagonal segments within r=26 of each room label classified all 25 rooms in one pass.
  Then take the zone boundary from the **heavy (w=1.68) dashed outline**, which sits exactly on the
  wall faces — the hatch is clipped to it.

- **🔴 A second sheet is the best audit of the first.** Translating A1 → FP1 (pure translation,
  DX=254.09 DY=158.94, both rotation-0 in the end) let every A1 room edge be tested against FP1's own
  face pairs. Two classes of error fell out of a takeoff I had already called complete and
  overlay-verified:
  - **Guard #15 (new): a correct TOTAL can hide a wrong SPLIT.** Equip 108 / IT 107 had been divided
    at **y = 727.9** — which is Corridor 109's south wall, *east of that block and not a wall inside
    it at all*. The real partition is the face pair at **781.1 / 786.7**. Equip 108 89.50 → **120.38
    SF**; IT 107 55.35 → **25.58 SF**. The two rooms' **sum moved by 1.10 SF**, so every total-based
    check passed while one room was 34% low and the other 54% high. **When you split a block into
    rooms, verify the DIVIDER against a face pair whose overlap actually spans the block — never
    extend a wall line in from outside it.**
  - **Guard #16 (new): decide the wall reference ONCE, and it is not the printed dimension.** Five
    rooms had one or two edges on the *far* face of the bounding wall, because the printed chain runs
    face-to-far-face — so "matches the printed 16'-4" exactly" *felt* like confirmation and was in
    fact the error. Classify each edge by asking whether the traced coordinate is the wall pair's
    **room-side** face or its far face. Storage 117 −8.51, Pano 110 −5.50, Storage 119 −3.90, Office
    103 −2.52, front-of-house −3.28 SF. Total 2,593.4 → **2,570.8 SF**.
  - **The reward:** FP1's OH-2 zone measures **75.46 SF** and the same two rooms traced independently
    on A1 now measure **75.43 SF** — two sheets, two extraction methods, **0.04 SF apart**. That
    agreement is the real verification; the earlier per-room "matches the printed dim" was not.

- **MEP6: separate the drawing by TONE before counting.** General Note D: *half-tone = existing to
  remain, full-tone/dashed = demolish.* `get_drawings()` splits cleanly — grey `(0.4/0.48)` 1,765
  paths vs black `(0,0,0)` 576. Every demolished device also carries a **grey fill dot ~5 pt**, which
  isolates devices from leaders and keynote bubbles in one filter. **7 devices — the carried total was
  right, the split was not**: 2 high bay + **1** bug-eye + **3** exit signs + 1 lighting control, not
  2/2/2/1. Separated by symbol-geometry signature at matched radius (exit sign 27–30 segments /
  29–32 pt of stroke; bug-eye 36 / 58). Same $110/EA, so **zero cost effect and a real scope fix.**

- **🔴 Guard #17 (new): the font-size discriminator cuts BOTH ways.** E1 earlier over-counted because
  a **12.57 pt legend key** was read as a device. E2 now proves the inverse: I had filtered MS tags to
  9.1 pt and counted **19**, while the sheet carries **23** `MS` strings. The four extras are **6.17 pt
  plain text labelling low-voltage homerun runs** — no symbol, sitting on a wire with tick marks. 19
  was right and 23 (which the estimate carried) was wrong, −$691. **Always histogram the tag population
  by font size, then RENDER A SAMPLE OF EVERY BAND before deciding which bands are devices.** Neither
  "the biggest band" nor "the modal size" is a rule.

- **Sheets that must stay unscaled, and why that is a measurement decision.** E4/E5/E6, M2/M3, P2–P5
  are NOT TO SCALE by their own title blocks. Leaving them without a plan scale is deliberate: a scale
  on a riser diagram lets someone take a real-looking measurement off a drawing with no geometric
  meaning. **Record the omission as intentional in the run log so the next person does not "fix" it.**

- **Architectural sheets in this set have ALL text outlined to curves** — `get_text()` returns zero
  spans on all ten. Every A-sheet fact must come from vector geometry or from rendering and reading.
  The MEP/E/FP sheets are ordinary text. **Check `len(page.get_text('dict')['blocks'])` first; it
  decides whether a sheet can be mined or must be looked at.**

- **Payload discipline held.** Both writes were generated end-to-end from source files
  (`e_final.json`, extracted face pairs) with `assert` on every count and rect before serialising —
  no hand-editing of a generated payload, per the fabricated-coordinate incident. `updateJob` is
  full-replace, so each edit re-sends all 72 parameters (~48 KB); budget for that, and keep a
  per-parameter coordinate checksum to verify the send.

- **State after run: 72 parameters, 24 geometry-anchored, across A1 / P1 / M1 / E1 / E2 / E3 / FP1 /
  MEP6.** Every trade with a scaled sheet is measured. Estimate requantified on the measured area:
  direct $806,102 → **$803,773**, bid $1,028,865 → **$1,025,931**; `validate_estimate.py` 0 FAIL with
  the xlsx tie-out passing.


### 2026-08-26 (d) — Job 2026-374 — I CALLED A CORRECT DRAWING WRONG (Guard #19) — Claude

The previous entry recorded that A0's 2,797 SF "project area" measured **8.1% high** against a traced
2,570.8 SF, and that finding went into a client bid proposal, the JobTread parameters and a PR body
before it was checked. **It was wrong. A0 is correct.**

- **What A0 actually is.** Its code summary breaks 2,797 SF into **Business 2,355 + Waiting 282 +
  Break 160** — a Revit room-area schedule, and Revit computes room areas at **wall centrelines**.
  Offsetting every traced room polygon outward by half a 4-7/8″ partition (2.82 pt at 13.5 pt/ft)
  and re-summing gives **2,794.7 SF against A0's 2,797 — 0.08% apart.**
- **So there was never a discrepancy at all**, only three references for the same 25 spaces: clear
  2,570.8 SF, centreline 2,797 SF, lease demise 2,544 SF (1.0% under clear, where a usable-area
  demise belongs). All three are right, each for its own purpose — A0 uses the centreline figure for
  an FBC Ch. 10 occupant-load calc, which is exactly what it is for.
- **Guard #19 (new): before declaring a stated quantity wrong, re-derive it on its own convention.**
  A one-line offset calculation would have caught this before publication. The tell was there in the
  arithmetic and I did not look: the gap was **226.2 SF**, and 431 LF of partition at 0.406 ft is
  **175 SF** of footprint, with the rest half the perimeter wall — that is a basis difference, not
  an error. **A number that is off by exactly a wall thickness is a reference problem, and reference
  problems are reconciled, not adjudicated.**
- **The requantifications survive, for a better reason.** Six line items were still on the wrong
  basis, because final cleaning, selective demolition, NFPA 13 sprinkler coverage, LVT, floor
  levelling and sealed concrete are all **floor** items and floor work is bought by the clear area.
  The money does not change; the justification changes from "A0 is wrong" to "these are floor items
  and A0 is a centreline figure."

**A6 Finish Plan — read the schedule, not just the plan (Guard #20).** A6 carries a full Room Finish
Schedule and it does not say LVT everywhere: **107 IT, 108 Equip, 117 and 119 Storage are CONC, and
110 Pano is VCT-1.** The LVT line was labelled *"NET room area"* and had never been netted for any of
them — **2,502 → 2,310 SF**, with floor levelling following its own note to 2,349 SF and sealed
concrete measuring 221 SF against 244. Base is B-1 in every room including the CONC ones; measured
gross room perimeter is **1,053.5 LF** against the 1,092 assumed, but the carried 944 LF was **left
alone** — the defensible deduction band (837–996 LF, depending on storefront glazing and casework)
is wider than the correction would be, and churning a quantity inside its own uncertainty is noise.

**A2 and A0 checked and clean.** A2's Equipment Schedule (102800) is 16 tags with a furnish/install
column; every CF/CI item is already priced and the OF/CI items correctly carry only blocking, mounts
and power. A0's remaining content — 46 occupants, two exits, 71′ max travel against 300′ allowed —
is already carried.

**State after run: 78 parameters, 23 geometry-anchored**, across A1 / P1 / M1 / E1 / E2 / E3 / FP1 /
MEP6. Direct **$806,102 → $801,789**; bid **$1,028,865 → $1,023,360**; `validate_estimate.py` 0 FAIL
with the xlsx tie-out passing.

### 2026-08-26 (e) — Job 2026-374 — THE LAST FOUR SCALED SHEETS WERE THE VENDOR'S — Claude

Closing pass. Verified the write (78 parameters, 23 geometry-anchored, all intact), then went after
the sheets I had not opened: A3/A4 interior elevations, A5 door schedule, and the seven Henry Schein
equipment sheets.

- **A5 settles the door count from the schedule, not the plan.** 13 rows, of which **three are marked
  EX** (existing to remain, verify and re-key) → **10 new doors**, matching the carried 10 doors / 10
  frames / 10 hardware sets exactly, and giving the hardware-group split 1/2/2/5 for free.
- **A3+A4 reconcile the casework to the foot.** Nine GC elevations, each with a printed dimension,
  sum to **85.08 LF** against a carried **85 LF**. The estimate turned out to carry one line per
  elevation with the printed dimension transcribed — so the check was a true independent re-add, not
  a re-read of the same arithmetic.
- **The scope boundary on A4 is the kind that loses money if skimmed:** the blue elevations say
  *"provided by Henry Schein and **installed by Contractor**."* Material excluded, labour ours. It was
  carried; but "Henry Schein casework EXCLUDED" in a line name is one word away from dropping the
  install.

**Guard #21 (new): a vendor sheet drawn to scale AND stamped NOT FOR CONSTRUCTION stays unscaled.**
Four of the seven HS sheets are ¼″=1′-0″ (SA.0 floor plan, SA.1 reinforcement, SP.1 plumbing, SE.1
electrical) and — unlike the InVision architectural sheets — carry extractable text, so they are
tempting. Each is stamped *"THIS SPECIFICATION SHEET IS A GUIDE ONLY… **NOT FOR CONSTRUCTION**"* and
*"**NOT AN ARCHITECTURAL PLAN**."* Putting a scale on them would let someone take a real-looking
measurement off a drawing its own author has disclaimed. **Mine the SCHEDULE, leave the plan
unscaled** — the same treatment as the NTS risers, for the same reason. Guard #18 says a scaled plan
with no measurements is unfinished; this is its exception, and the exception has to be *recorded* or
the next pass "fixes" it.

**Guard #22 (new): a parse that drops rows manufactures gaps.** A column-position extractor over the
SE.1 schedule silently missed **eight** rows and reported specs **6B, 14A and 39B** as uncosted. All
three are correctly not separate scope — 6B dental lights and 39B chair-mounted monitors are both
*"tied in at power for chair"*, and 14A's two autoclaves sit inside the estimate's "sterilizers (3)".
**Reconcile the parse against its own row count before reporting a gap, then read the schedule.** I
came within one sentence of putting three fictitious scope gaps in front of a client.

Every HS spec item reconciles: 35 blocking ×9 (plan tags confirm 9), 9C pano, 3A/4C/5 ×7 at the
chairs, 23A exhaust fan → the Greenheck EF-3 with the rate-of-rise thermostat the spec demands, and
23A's *supplemental cooling* clause → the Mitsubishi 3-ton split, which matters because the compressor
and vacuum throw ~19,000 BTU/h into Equip 108.

**One drawing defect worth an RFI:** A3 titles an elevation "Break **121**" (Break is 125) and A4
titles two "Labratory **109**" (Lab is 112, and it is misspelled). The estimate had already
reconciled them; a GC working straight off the elevations would not.

**Takeoff COMPLETE.** All 38 sheets accounted for: 11 traced or measured, 8 verified with no change,
19 correctly unscaled (NTS details, risers, schedules, specs, and the four not-for-construction
vendor plans). No parameter changed in this pass — nothing measured moved.

### 2026-08-26 (f) — Job 2026-374 — I VERIFIED WHAT WAS DRAWN, NOT WHAT WAS REQUIRED — Claude

I closed the previous entry with "Takeoff COMPLETE. All 38 sheets accounted for." That was wrong in a
way worth recording: I had verified every **drawing** and never mined the **specifications**.

**The tell was countable and I never counted it.** Grepping citations per sheet across the estimate:
MEP5 appears 13 times, MEP6 19 times, and **MEP1, MEP2, MEP3 and MEP4 appear zero times**. Four
specification sheets had never been opened. A7 and A8 had been (they are cited throughout), which is
what made the set *look* covered.

Reading them found **eight required items with no line, $15,570 of direct cost** — and for the first
time in this whole review the bid went **up**, from $1,023,360 to $1,042,947.

- **MEP4 is an entire sheet devoted to SECTION 260573** — short-circuit study (IEEE 399/551),
  overcurrent coordination study (IEEE 242) and arc-flash hazard analysis (IEEE 1584 / NFPA 70E),
  **performed by a PE employed by the panelboard manufacturer** (a third-party engineer is expressly
  not accepted), plus NETA ETT Level III field adjusting with ATS testing on every adjustable OCPD,
  machine-printed arc-flash labels, and Owner training. **$7,500.**
  **Guard #24 (new): "implied and not scoped" is a claim to verify, not a conclusion.** The estimate
  had recorded exactly that, inferring the study from a "SCCR per study" note on a panel schedule
  rather than finding the dedicated section that mandates it. Also buried in §1.1 B: *"Equipment AIC
  ratings for coordinated equipment shall be as required by the results of the fault current study **at
  no additional cost**"* — a risk transfer that belongs in the qualifications, not a footnote.
- **MEP2 §12.0**: duct liner/wrap on all low-velocity rectangular supply and return duct. Div 23
  carried 870 lb of *bare* galvanised duct and a single lined return boot. 860 SF, **$2,550**.
- MEP3 §13.0: plumbing systems testing ($1,700) and domestic water sterilisation with lab results
  ($650). MEP2 §220100 G.6: NFPA 99 dental gas testing and certification ($1,600) — NFPA 99 appeared
  twice in the estimate *descriptively* with no testing line. MEP3 §260100 11.0: electrical
  identification ($960). MEP2 §16.0: escutcheons ($440). MEP1 §8.0: spare filter sets ($170).

**Guard #23 (new): count citations PER SHEET across the whole estimate.** It is a two-line grep and it
finds unread sheets instantly. Verifying what is *drawn* is not verifying what is *required*; the
geometry pass and the specification pass are different jobs and finishing one is not finishing the other.

**Guard #25 (new): resolve cross-referenced sheet numbers against the delivered set.** SA.1, SP.1 and
SE.1 each say *"SEE SHEETS SED.1 – SED.3"*; the package delivers SCV, SA.0, SA.1, SP.1, SE.1, SED.1
and SED.2. **SED.3 does not exist in the set**, and eleven line items are priced against it. RFI raised.

**Priced neither way, deliberately:** MEP3 §260100 4.0 B demands NEC 517.13 patient-care grounding,
but NEC 517.10(B) exempts Category 3 (Basic Care) spaces, which is how dental operatories are normally
classified. Roughly $1,900 if it applies. Disclosed as an RFI rather than silently priced or silently
dropped — the spec and the code disagree and that is the EOR's call, not mine.

**Verified clean:** S1 structural (Div 05's seven lines map one-for-one to its details; special
inspections correctly a documented zero, Owner-employed per S1 §3.C) and A8 §099123's dryfall
requirement (0 SF is right — RCP note 1 puts ACT or GYP everywhere, nothing is open to structure).

**No JobTread parameter changed**: nothing *measured* moved. These are specification scope findings and
they live in `lineitems.csv` and the takeoff.

### 2026-08-26 (g) — Job 2026-374 — WITHDRAWING THE SED.3 RFI I RAISED ONE ENTRY AGO — Claude

The previous entry raised, and I reported to the user, that Henry Schein sheet **SED.3 was never
delivered** and that eleven line items were priced against a sheet nobody had. **That was wrong and I
have withdrawn it.**

Resolving every detail number against the two delivered sheets:

| Sheet | Details it carries |
|---|---|
| **SED.1** | 3A, 4C, 9B, 9C, 13, 14A, 14C, 14E, 15B |
| **SED.2** | 16, 25, 27, 29A, 30, 31A, 32, 35 |

**Every detail the drawings actually reference is present.** The *"SEE SHEETS SED.1 – SED.3"* line on
SA.1/SP.1/SE.1 is vendor boilerplate naming a range, not a promise of a third sheet. What was really
wrong was **our own citation hygiene**: fourteen references pointed at the wrong sheet — thirteen
calling SED.2 details "SED.3", one calling a SED.1 detail "SED.2", and one citing a "detail 5" that
exists nowhere (spec 5 is scheduled on SE.1 and has no detail). All repointed; the bid is unchanged
because only citations moved.

**Guard #25 rewritten.** It said "resolve every cross-referenced sheet number against the delivered
set and RFI the gaps." The sharper and more honest version: **resolve the reference before raising the
RFI — a citation to a sheet that is not in the set is evidence of a bad citation at least as often as
evidence of a missing document.**

**What actually went wrong in my process.** I wrote Guard #22 earlier in this same review — *a parse
that drops rows manufactures gaps; reconcile before reporting* — after nearly reporting three
fictitious scope gaps on the SE.1 schedule. Then I turned around and shipped exactly that failure
mode on SED.3: I confirmed the sheet was absent from the package and stopped there, without checking
whether anything it was supposed to contain was actually missing. **Confirming the absence of a label
is not confirming the absence of the content.**

The method that keeps working is the boring one: enumerate both sides and reconcile them. It found
the real gap (MEP1–MEP4, $15,570) and it dissolved both false ones (SE.1 specs 6B/14A/39B, and this).

**How the set stands.** Every one of the 38 sheets now carries three or more citations in the estimate,
which was the check that exposed the unread MEP specs in the first place.

### 2026-08-26 (h) — Job 2026-374 — THE SCHEDULE PASS, AND A FEE PRINTED ON THE DRAWING — Claude

Entry (f) closed the specification axis; entry (g) withdrew a bad RFI off it. This entry closes the
last axis I had not enumerated: **the schedules**. A sheet citation proves the sheet was *opened*, not
that every row on it was priced — so all six schedule sheets were reconciled mark by mark against the
line items.

**Five of six were clean, and cleanly so.** MEP5's five equipment schedules including the footnote-only
items (seacoast-coated coil, waffle pads, PLT-12 expansion tank, and the RTU note that says *replace
the existing 50 A breaker with 30 A and replace the disconnect* — a schedule footnote with no plan
symbol, already carried). M3's six diffuser marks plus after-hours core drilling and GPR floor
scanning. P5's ten fixture marks down to the Trubro lav guard and the Haws eye-wash. E5's three
panels. **That is the boring outcome the method is supposed to produce, and it is worth recording that
it produced it** — a reconciliation that finds nothing is evidence, not wasted effort.

**E6 was not clean, and the defect was commercial rather than dimensional.** Its substitution notes,
printed twice on the sheet, state: *"for each and every type of light fixture or control system
offered as an unsolicited alternate, a $500.00 fee will be charged to the contractor for review …
in no way a guarantee of approval … must be received by the engineer prior to any review commencing."*

**ALT-9 is exactly one fixture type offered unsolicited.** The proposal published it as a **($572)**
deduct and told the client *"the $572 deduct is trivial — take it for the lead time."* Net of the fee
the alternate is worth **($72)**. The reasoning was right; the number was wrong by a factor of eight,
in the client's disfavour, inside a document that promises "the honest verdict on each rather than a
sales pitch." Restated to ($72) with the fee disclosed and a withdrawal option offered. Group B
+$7,952 → **+$8,452**; all ten $1,071,527 → **$1,072,027**, $416.80 → **$417.00/SF**. **Base bid
unchanged at $1,042,947** — ALT-9 sits outside it, and no other alternate is a lighting substitution.

**Guard #26 (new): a drawing sets COMMERCIAL terms as well as technical ones.** I had been reading
sheets for geometry, then for specified scope, and never for **conditions of bidding**. Substitution
deadlines, review fees, separate-pricing rules and post-bid-alternate terms are priced scope. The
sharpest form: **a fee that attaches to something you volunteered is a cost you chose** — and the
alternate that triggers it has to be re-justified after the fee, not before.

Two further E6 conditions now carried: substitution requests are due **10 days before bid**, and
*"failure to submit constitutes a guarantee to supply the specified light fixture"* — every fixture
line is priced on the basis of design, so this is satisfied, but it hard-locks the lighting buyout and
is *why* ALT-9 must run post-bid and pay. And lighting controls pricing must be **"completely separate
of any light fixture pricing"** or it is *"immediately rejected in its entirety"* — satisfied
structurally, controls in 260923, fixtures in 265119, exit signs in 265300, never bundled.

**Where the takeoff now stands.** Three axes enumerated and reconciled: **geometry** (every scaled
sheet traced and overlay-verified), **specification** (every sheet cited three or more times), and
**schedule** (every mark on every schedule reconciled). Two RFIs remain open and both are genuinely
the EOR's call, not mine: NEC 517.13 patient-care grounding (~$1,900 if the operatories are Category
1 or 2) and MEP6 keynote DP03 (~$505 if it is a second waste stub to cap).

### 2026-08-26 (i) — Job 2026-374 — THE FOURTH AXIS, AND A RETRACTION THAT DID NOT TAKE — Claude

Entry (h) closed the schedule axis and claimed three axes were enumerated. There was a fourth:
**the general-notes block**. Each discipline publishes exactly one, stamped *"(TYPICAL ALL SHEETS)"* —
M3 for mechanical, P5 for plumbing, E6 for electrical, FP1 for fire protection — so four blocks govern
all 31 engineering sheets, and reading them is cheap once you know that.

Three of the four were clean. E6's is the densest on the job (notes A through V) and is where the
ALT-9 review fee in entry (h) came from; everything else on it reconciles, including the full fire
alarm modification scope and the 15 dBA-above-ambient audibility verification with horns added as
required.

**Four apparent gaps came out of the grep and all four were correctly not separate scope** — guard 22
applied to my own output rather than to someone else's schedule. Rated box enclosures were already
inside the firestopping allowance under different wording. Fire cap housings at rated *ceilings* are
zero because the rated assembly here is a **wall**. Existing-device replacement is inapplicable to a
bare first-generation shell. Dry sidewall at vestibules was already a *documented zero* in the
takeoff — my grep had searched the line items and the answer was in the other file. **Four for four
is the expected outcome of a good process, and worth recording as such:** a reconciliation that finds
nothing is evidence, not wasted effort.

**What the pass did find was mine.** Two rows of `lineitems.csv` still asserted, as fact, that
*"A0 is 8.1% high"* — the claim withdrawn in entry (e) when A0 turned out to be a correct centreline
figure. The narrative had been corrected everywhere. The **derived basis notes had not**, and those
are the text a client reads sitting next to a price. Both rewritten; no quantity or price moved.

**Guard #27 (new): a retraction is not complete until every derived copy is gone.** I corrected the
document that made the argument and never grepped the withdrawn phrase across the deliverables that
had quoted it. The fix is mechanical and takes one command: **grep the withdrawn claim itself, not the
document that carried it.**

That is the third time in this review the same shape has appeared — publish, then verify. Guard 19
(A0), guard 25 (SED.3), guard 27 (the retraction). The through-line is not carelessness about facts;
it is **treating "I have corrected this" as an event rather than as something to check**.

**Where the takeoff stands.** Four axes enumerated and reconciled: **geometry**, **specification**,
**schedule**, **general notes**. Base bid $1,042,947. Two RFIs remain open and both are genuinely the
EOR's call: NEC 517.13 patient-care grounding (~$1,900 if the operatories are Category 1 or 2) and
MEP6 keynote DP03 (~$505 if it is a second waste stub to cap).

### 2026-08-26 (j) — Job 2026-374 — THE KEYNOTE PASS, AND A TABLE THAT HAD QUIETLY STOPPED TYING — Claude

Fifth axis: **plan keynotes**. Extract every keynote ID per sheet, reconcile against the estimate.
Six of 66 came back uncited. Five resolved as covered or as coordination instructions carrying no
cost — P13 *route piping clear of new electrical*, E17 *coordinate mounting in the casework niche*,
E13 *hand dryer* (carried at row 117, cited by its A2 schedule tag not its keynote).

**E28 was real.** *"TOGGLE SWITCH TO CONTROL EXHAUST FAN."* Row 231 had recorded *"exhaust fans
integral"* and carried no device — treating the factory integral **disconnect** at the fan as
satisfying a **control** switch on the wall. Corroborated three ways that agree exactly: MEP5 puts
electrical note B on **EF-1 and EF-2 only** (EF-3 carries note A alone), E2 places **exactly two** E28
tags, and there are **exactly two** toilet rooms. EF-3 needs no toggle because its control *is* the
rate-of-rise thermostat — keynote E26, furnished under Div 23 *"to the electrical contractor for
installation"* with no Div 26 line for that installation. One line, 3 EA, **$485 direct**.

**Guard #29: when a schedule note and a plan keynote both name a device, they are naming a device.**

**Then the small line exposed a large one.** The published cost-by-division table in the estimate
summary, and its short form in the proposal, **summed to $806,101 over 262 line items** — the state
*before the specification review*, three revisions back. Nine of nineteen divisions were wrong,
Electrical worst at $144,341 published against $152,595 actual.

**What makes this worth a guard is why nobody caught it.** The table's *internal* arithmetic was
flawless: every loaded column was exactly its direct × 1.27634, and that factor reproduces the
original $1,028,865 bid perfectly. **A stale table that is self-consistent passes every check you run
inside it.** The only visible tell was a bold total row reading "262" beside a 271-row total, because
successive find-and-replace passes on the headline had been dragging the total row forward while
leaving every division row behind. The $/SF columns had also split bases — division rows on 2,797 SF
gross, total row on 2,570.8 SF clear, in one table.

**Guard #28: regenerate derived tables from the source; never patch them.** A find-and-replace on a
headline figure updates the sentences that quote it and silently desynchronises every table that
derives from it.

Both tables regenerated from `lineitems.csv` on one area basis, with the dependent narrative
recomputed — cost-type split, the four cost drivers, Div 26+27+28 concentration (**$197,718 direct,
24.2%**), and the mandated-vendor exposure rebuilt from its three components to **$86,973 at sell,
8.3% of bid**. A cross-document tie-out now runs: both tables sum to $817,844 over 271 rows,
percentages foot to 100%, all four documents carry the same bid.

**One count I tried to improve and deliberately did not.** Row 214's 108 general-use receptacles are
a *derived* count (panel VA ÷ 180, NEC 220.14(I)), disclosed as such with a field-verify note and a
stated sensitivity of ≈$114/outlet — ~$12,300 of exposure, worth attacking. **E1 defeated it
honestly:** the sheet is flattened to **55,224 individual line segments**, every symbol exploded, so
the symbol-signature clustering that split exit signs from bug-eyes on MEP6 has nothing to cluster.
Producing a confident-looking count from that is guard 14 in its purest form. Corroborated instead
from three directions that agree — 64 receptacle circuits on the panel schedules, 69 non-default
mounting-height tags on E1, 144 devices carried at 2.2 per circuit against an NEC ceiling of 13
(the expected shape where equipment takes dedicated circuits). **The derived count stands, disclosed.**
Recording the negative result matters: *"I could not measure this and here is what I checked instead"*
is a takeoff finding, and leaving it unsaid is how a soft number gets read as a hard one.

**Where it lands.** Direct $806,102 → **$817,844**; bid $1,028,865 → **$1,043,566**. Five axes
enumerated: **geometry, specification, schedule, general notes, keynotes**. Two RFIs stay open and
both are the EOR's call: NEC 517.13 patient-care grounding (~$1,900) and MEP6 keynote DP03 (~$505).

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
