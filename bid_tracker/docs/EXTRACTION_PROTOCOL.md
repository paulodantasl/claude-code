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
   - `project_type`: V-TI / V-REN / V-ADA / V-NEW-S / V-NEW-L / V-ENV / V-MEP / R-* (see README).
   - `award_basis`: `low_bid` for ITBs; `best_value` for scored RFPs; `rate_card` for unit-rate term contracts.
   - `ee_source`: `ee` only when the document calls it an engineer's / architect's estimate; a "budget" or
     "available funding" is `budget`.
   - `gsf` only when the documents state it (`stated`) or you measured it from plans (`measured`).
6. Run `python3 -m bid_tracker validate <package>`. Fix every ERROR; read every WARN.
7. Import: `python3 -m bid_tracker import-csv <package> --feed manual`.

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
