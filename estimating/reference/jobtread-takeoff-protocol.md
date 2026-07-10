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
