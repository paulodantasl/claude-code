# Harvest protocol — finding Florida bid tabs

Phase 1: Tampa Bay vertical building (TI, renovation, ADA, small new buildings) and disaster/restoration
term contracts, 2023 onward. Agencies and portals are in `reference/agencies.csv` (`watch=1` = check every run).

## Where tabs live (confirmed by fetch, 2026-10)

| Agency | Where the numbers are | How |
|---|---|---|
| City of Tampa | Contract Administration bid tabs (construction-project-bidding listing); Purchasing ITB awards in Council backups | PDFs under `tampa.gov/sites/default/files/bid/docs/`; `tampagov.hylandcloud.com/251agendaonline` item attachments |
| Hillsborough County BOCC | board backup PDFs with the tab | `eagenda.hcfl.gov`; Bonfire past opportunities |
| Pinellas County BOCC, Clearwater, Pinellas Park | award items with the tab attached | Legistar Web API `webapi.legistar.com/v1/<client>/matters` (clients `pinellas`, `clearwater`, `pinellaspark`); attachments on `<client>.legistar1.com` |
| St. Petersburg | Council agenda packets / Numbered Action Taken | stpete.org links to `cms5.revize.com/revize/stpete/<file>.pdf` |
| OpenGov agencies (Pinellas Schools, Seminole, Brevard Schools) | tabulation attachments | the public API `api.procurement.opengov.com/api/v1/project/<id>`, only while it answers without a challenge, token or login |
| Polk County BOCC | "Submittals Received" + "Recommendation of Award" PDFs | `polkfl.gov/wp-content/uploads/`; WordPress REST API |
| City of Lakeland | bid tabs | `lakelandgov.net/media/<id>/<no>-bid-tab.pdf` (recent tabs only on the listing page) |
| Pasco County BOCC | tabs and memos | CivicClerk tenant `pascocofl` (`pascocofl.api.civicclerk.com`); Bonfire past list JSON |
| Pasco County Schools | award attachments | IonWave `pascok12.ionwave.net` public Awarded Bids |
| Lee County BOCC (restoration) | agenda item reports + price analyses; awarded list | `leecofl.api.civicclerk.com`; IonWave `leegov.ionwave.net` |
| Manatee County | board items, minutes | `agendaonline.mymanatee.org`; `records.manateeclerk.com` |
| Port Tampa Bay | board award items | BoardBook (`meetings.boardbook.org`, org 1448) |
| City of Sarasota | Commission agenda items | `sarasota.granicusideas.com` |
| Citrus Schools | notices of intent with the tab | VendorLink `vfile` PDFs |

**Not readable by script; don't try to get around it:** `tampaairport.com` (Cloudflare), `scgov.net` (Akamai),
OpenGov portal HTML (Cloudflare), `public.mymanatee.org`, `myclearwater.com`, Bonfire detail pages,
`manateeschools.net`, `go.boarddocs.com`, `bidbanana.thebidlab.com`. Use the agency's board-agenda system
instead, or list a Ch. 119 request. A source in the table above counts only while it answers the tool's own
User-Agent (`ideal-bid-tracker/0.1 (public records research)`) without a challenge or login; never retry
with a browser User-Agent, changed headers or a headless browser.

No public listing → list the Chapter 119 request in the run report; Paulo sends it (USF; HCAA tabs;
Hillsborough/Polk/Sarasota Schools; Pinellas Schools term contracts behind the OpenGov login).
`records_requests` is not replayed by `rebuild`, so don't rely on it between runs.

## Search patterns that work

- `"bid tabulation" <agency> <year> renovation`, `"tabulation" "ITB" <agency> restroom`
- `"intent to award" <agency> <project>`, `"recommendation of award" <agency> <year> construction`
- Board agendas: `site:<agenda host> "award" "bid" renovation`
- Disaster contracts: `"disaster" "remediation" "term contract" <county> award`, `"emergency restoration" "rate sheet" <city>`

## Per-run checklist

`/bid-tabs weekly` runs this (see `.claude/commands/bid-tabs.md` for the exact commands):

1. For each `watch=1` agency, check postings, board agendas and award notices from 120 days before the
   agency's newest `bid_open_date` (or 120 days back if it has none); retry `private/holdback.csv`.
2. Extract each new tab per EXTRACTION_PROTOCOL.md into `staging/<run date>-<agency>/` and validate it
   against a copy of `bids.db` (0 errors).
3. Independent check of every package: a second reader re-derives every bidder and total from the saved
   source, then one repair pass and one recheck. A package that still fails stays in staging/ and goes in
   `private/holdback.csv`.
4. Move passing packages to `packages/<run date>-<agency>/`, `import-csv --feed weekly`, then merge only
   clear same-firm spellings (`bidders review`, `bidders merge`).
5. Commit and push the data repo.
6. Notion sync per NOTION_SYNC.md, ending with `export-notion` reporting 0 ops; commit `notion_map.csv`
   after every `notion-ack`.
7. List Ch. 119 requests still needed in the report. Paulo sends them; the weekly run never does.

## Quality bar for the seed

≥40 solicitations · ≥70% `official_tab` or `board_award_item` · ≥30 with every bidder · ≥15 vertical with GSF ·
≥5 rate cards · 0 validator errors.
