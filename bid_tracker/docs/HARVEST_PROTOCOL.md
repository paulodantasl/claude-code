# Harvest protocol — finding Florida bid tabs

Phase 1: Tampa Bay vertical building (TI, renovation, ADA, small new buildings) and disaster/restoration
term contracts, 2023 onward. Agencies and portals are in `reference/agencies.csv` (`watch=1` = check every run).

## Where tabs live (search-confirmed 2026-10; verify on first fetch)

| Source | What you get | Format |
|---|---|---|
| City of Tampa — Contract Administration | full bid tabs, 2013– | PDF under `tampa.gov/sites/default/files/bid/docs/` |
| City of Tampa / Sarasota County / Pinellas Schools / St. Pete — OpenGov | Results tab: tab, awardee, award date | JS page (St. Pete needs free login) |
| Hillsborough County BOCC — Bonfire | past opportunities (if enabled) | HTML/PDF |
| Tampa International Airport (HCAA) | Notice of Intent to Award with tab | PDF |
| Port Tampa Bay | monthly contract-award pages | HTML |
| Manatee County | board backup (clerk records), DemandStar | PDF |
| Board agenda systems (Legistar etc.) | award items with the tab attached | JSON API + PDF |
| FDOT (horizontal, phase 2) | letting results, bid tabs, item average costs | PDF / XLSX |

No public listing found → file a Chapter 119 request and log it in `records_requests`
(USF, Hillsborough BOCC, Polk County, Hillsborough Schools).

## Search patterns that work

- `"bid tabulation" <agency> <year> renovation`, `"tabulation" "ITB" <agency> restroom`
- `"intent to award" <agency> <project>`, `"recommendation of award" <agency> <year> construction`
- Board agendas: `site:<agenda host> "award" "bid" renovation`
- Disaster contracts: `"disaster" "remediation" "term contract" <county> award`, `"emergency restoration" "rate sheet" <city>`

## Per-run checklist

1. For each `watch=1` agency, look for tabs/awards posted since the last run (Bid Pricing Updates in Notion has the date).
2. Extract each new tab per EXTRACTION_PROTOCOL.md into `$BID_TRACKER_DATA/packages/<date>-<agency>-<slug>/`.
3. `validate` → `import-csv --feed weekly`.
4. Spot-check: one subagent re-reads 10% of new rows against the source.
5. `export-notion` → apply → `notion-ack`; commit and push the data repo.
6. Missing winners' cost sheets for jobs Ideal bid: send the Ch. 119 request, log it.

## Quality bar for the seed

≥40 solicitations · ≥70% `official_tab` or `board_award_item` · ≥30 with every bidder · ≥15 vertical with GSF ·
≥5 rate cards · 0 validator errors.
