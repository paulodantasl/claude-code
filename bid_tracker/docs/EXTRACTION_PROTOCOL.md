# Extraction protocol — bid-tab PDF to import package

Applies to whoever turns a tabulation into rows: a person, or a Claude subagent. The validator catches
arithmetic and sourcing slips. It cannot catch a misread digit that still adds up, so the steps below exist.

## Rules

1. **Never guess.** A blank beats an estimate. If a value isn't on the page, leave it empty and say why in `notes`.
2. **Copy verbatim.** Bidder names exactly as printed (`bidder_name_raw`); amounts to the cent.
3. **Quote your source.** `source_excerpt` holds the line(s) the award / low bid came from, as printed
   (e.g. `Low bidder: Acme Builders, Inc. $812,400.00`). The validator checks the number is in it (E-NOSRC).
4. **Cite the page.** `page_ref` on every bid row (`p2`, `p2-3`).
5. **One solicitation, one source of truth.** Use the official tab or the board award item over news.
   Record any second document in a later package; the importer keeps the stronger one.

## Steps

1. Save the PDF to `$BID_TRACKER_DATA/raw/<agency_id>/` (gitignored there too if large; the URL is what's kept).
2. Read it page by page (visual read). Then cross-check with `python3 -m bid_tracker pdf-text file.pdf --pages 1-3`.
   Scanned pages have no text layer — read them visually and write `scanned` in `notes`.
3. Fill `solicitations.csv` (one row) and `bids.csv` (one row per bidder). Add `bid_items.csv` when the tab
   shows unit prices, `rate_cards.csv` for term/disaster rate sheets, `agencies.csv` for an agency not in
   `reference/agencies.csv`.
4. **Re-read the three lowest totals** against the page a second time. These drive every benchmark.
5. Classify:
   - `project_type`: V-TI / V-REN / V-ADA / V-NEW-S / V-NEW-L / V-ENV / V-MEP / V-PARK / R-* (see README).
     Parking garages and decks are V-PARK, not V-REN: their $/SF runs an order of magnitude below a building remodel's.
   - `award_basis`: `low_bid` for ITBs; `best_value` for scored RFPs; `rate_card` for unit-rate term contracts.
   - `ee_source`: `ee` only when the document calls it an engineer's / architect's estimate; a "budget" or
     "available funding" is `budget`.
   - Square footage goes in `areas.csv`, not in `gsf` (see **Square footage** below).
6. Validate against a copy of the live DB (a fresh `--db` path would hide duplicate-name warnings):
   `cp $BID_TRACKER_DATA/bids.db /tmp/<group>.db && python3 -m bid_tracker --db /tmp/<group>.db validate <package>`.
   Fix every ERROR; read every WARN.
7. Don't import. Hand the package to the coordinator, who imports it with `import-csv` only after an
   independent check (`/bid-tabs` step 3).

## Fetching

Use the tool's own User-Agent (`ideal-bid-tracker/0.1 (public records research)`). A 403/429, challenge
page, CAPTCHA or login means the source is blocked: stop, log it, use the agency's board-agenda system or a
Ch. 119 request. Never retry with a browser User-Agent, changed headers or a headless browser.

## Field notes

- **No opening date in the source?** Use the date the source does give and set `date_basis` to `award`,
  `board` or `posted`, with a one-line note. Never estimate a date.
- **Page blocked, only a search snippet?** `evidence_class=search_snippet`, `source_url` = the result's URL,
  `source_excerpt` = the snippet text containing the number, verbatim. Mark `notes` "snippet only; verify".
  These rows are replaced automatically when the official document is imported.

- **Alternates.** Put each in `alternates_json` (`{"Alt 1": 12500, "Alt 2": -4000}`) and set `total_basis`
  to how the agency ranked: `base`, `base+all_alts`, `base+accepted_alts`, or `as_tabulated`.
- **Non-responsive / withdrawn** bidders: keep the row, set `responsive=0` or `withdrawn=1`.
- **Award to someone other than the low bidder:** say why in the solicitation `notes` (E-LOW requires it).
- **Multiple awards** (term contracts): set `is_awardee=1` on each awarded bidder; leave `awardee_name` blank.
- **Not-to-exceed awards:** `award_is_nte=1`; they are excluded from low-bid statistics.
- **Rate cards:** one row per bidder × service × size bucket. `unit` = `sf`, `lump`, `hr`, `day`, `each`.
  Each row's `source_excerpt` quotes that cell (`Mold 10,001+ sf: $14.00/sf`).

## Square footage (`areas.csv`)

Every per-project vertical tab (V-*, not a term or rate-card contract) needs an area row or an entry in
`D/area_misses.csv` saying where you looked. $/SF benchmarks only use tabs with an area.

**What the area measures (`area_kind`).** $/SF only compares like with like, so say what the number is:
- `scope_area`: the area the contract price covers. That's the renovated area for V-REN / V-TI / V-ADA,
  and the gross area for a new building.
- `roof_area`: roof surface replaced (V-ENV). Convert roofing "squares" × 100 only when the document says squares.
- `building_gsf`: the whole building's gross area, when that is all you can find for a partial renovation.
  Keep looking for the scope area; record both if you find both (one row per kind).

Which kind a tab's $/SF uses: V-NEW-* building_gsf then scope_area; V-REN/V-TI/V-ADA scope_area only (a
whole-building figure on a partial remodel would make $/SF meaningless; a remodel of the entire building
records that area as scope_area); V-ENV roof_area then scope_area; V-MEP building_gsf then scope_area; V-PARK scope_area (the deck area repaired).
Other kinds are still worth recording: they show on the tab and help the next search.

**Where to look, in order** (stop at the first scope or roof area from an official record):
1. The solicitation documents you already saved: invitation to bid, Summary of Work (01 10 00 / 01 11 00),
   bid-form quantities, addenda. `grep -il "sq\.\? *ft\|square f\|\bSF\b\|GSF\|squares"` over the text.
2. The drawings: cover, G-001 or the code-data / life-safety sheet ("BUILDING AREA", "AREA OF ALTERATION").
   Read scanned sheets visually.
3. The award's agenda memo and its backup (Legistar / Hyland). A/E proposals in the backup often state the area.
4. The job's building permit (city or county permit portal): "Project Area SQ FT" on the permit record.
5. The county property appraiser's building card (whole building only, `building_gsf`, basis `derived`).
   Only for a job covering the whole building, and only if the host is reachable; never past a wall or login.
6. Measure it: when the plans are public but print no area, measure the scope from a scaled floor plan
   (basis `measured`; `notes` must give the sheet, the scale and the dimensions used).

**Each row:**
- `sf`: copied exactly.
- `basis`:
  - `stated` (printed in an official record for this job);
  - `measured`;
  - `derived` (appraiser or another record about the building, not the job, or a sum of areas quoted
    together, e.g. two buildings in one contract).
- `source_url` and `source_page`: the document and page or sheet.
- `excerpt`: the line containing the number, verbatim. The validator checks (E-NOSRC):
  - a stated `sf` appears in the excerpt, or appears as roofing squares × 100 when the excerpt says squares;
  - a derived `sf` appears, is a sum of 2-4 figures quoted there, or is the total of every figure quoted with
    an area unit (a roof-section schedule printed without a total).
- An independent checker re-opens the cited page before import, the same as for bid totals.

A stronger basis replaces a weaker one for the same kind (stated > measured > derived). An area row is kept
when the solicitation is later updated, so re-harvesting a tab never erases its area.

**Nothing found?** Add `sol_ref, searched, last_tried` to `D/area_misses.csv` (searched = the sources you
tried, `;`-separated). The harvest retries it after 90 days. List it in the report with a one-line Ch. 119
request for the plans' code-data sheet.
