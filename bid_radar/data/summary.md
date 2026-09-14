# Tampa Bid Radar — permit signals

Collected 2026-09-14T01:23:28+00:00 · 90-day window by application date (CREATEDDATE) · source [City of Tampa PermitsAll](https://arcgis.tampagov.net/arcgis/rest/services/Planning/PermitsAll/FeatureServer/0)

- 29 commercial records in the window
- **13** fitout-capable records inside a tracked submarket — **13** of them filed in the last 90 days
- **4** qualified (score ≥ 55, no hard blocker)
- **3** at EARLY START, where buyout is still open

> **What this source can tell you.** The layer publishes permits at issuance — it has no application or in-review stage — so a row here is a job that is already permitted, unless it is tagged `early_start`: there the city has released interior non-structural work while the main permit is still pending, and the rest of the scope is still being bought out. Intake to issue ran 15-66 days (median 35) across the most recent commercial records. The layer carries no valuation, applicant, owner or contractor field, so those columns are absent rather than guessed; the tenant is parsed out of the project name and description and is blank where it could not be read with confidence.

## By submarket × trade

| Submarket | restaurant | retail | office | other | total |
|---|---|---|---|---|---|
| Water Street | 1 |  |  | 1 | **2** |
| Downtown Riverwalk |  |  | 2 |  | **2** |
| Dale Mabry |  |  | 3 |  | **3** |
| Airport / Westshore |  | 1 | 5 |  | **6** |

## Qualified — call these (4)

Score at or above 55/100 with no hard blocker (PLAN §2.3/§2.4). `needs_contact` on a row means the entity is named but the permit layer carries no phone or email — that is every permit row, and it is what the alcoholic-beverage layer fixes in Phase 2.

| Permit | Filed | Stage | Submarket | Trade | Score | Tenant / project | Address | Flags | Source |
|---|---|---|---|---|---|---|---|---|---|
| `BLD-26-0526061` | 2026-06-22 | early_start | Water Street | restaurant | **73** | Wagamama Pan Asian | 1050 Water St | needs_contact | [record](https://aca-prod.accela.com/TAMPA/Cap/CapDetail.aspx?Module=Building&TabName=Building&capID1=26CAP&capID2=00000&capID3=01TOI&agencyCode=TAMPA) |
| `BLD-26-0526342` | 2026-07-06 | early_start | Airport / Westshore | retail | **63** | Edikted | 2223 N West Shore Blvd | needs_contact | [record](https://aca-prod.accela.com/TAMPA/Cap/CapDetail.aspx?Module=Building&TabName=Building&capID1=26CAP&capID2=00000&capID3=01W3M&agencyCode=TAMPA) |
| `BLD-26-0526369` | 2026-07-06 | revision | Downtown Riverwalk | office | **58** | Altieri Ins. Consultants | 400 N Tampa St #FS | needs_contact | [record](https://aca-prod.accela.com/TAMPA/Cap/CapDetail.aspx?Module=Building&TabName=Building&capID1=26CAP&capID2=00000&capID3=01WDJ&agencyCode=TAMPA) |
| `BLD-26-0525940` | 2026-06-17 | revision | Airport / Westshore | office | **58** | Nationwide | 4200 W Cypress St | needs_contact | [record](https://aca-prod.accela.com/TAMPA/Cap/CapDetail.aspx?Module=Building&TabName=Building&capID1=26CAP&capID2=00000&capID3=01SVA&agencyCode=TAMPA) |

## EARLY START — main permit still pending, buyout open (3)

The city has released interior non-structural work while the main permit is in review. The rest of the scope is still being bought out.

| Permit | Filed | Stage | Submarket | Trade | Score | Tenant / project | Address | Flags | Source |
|---|---|---|---|---|---|---|---|---|---|
| `BLD-26-0526342` | 2026-07-06 | early_start | Airport / Westshore | retail | **63** | Edikted | 2223 N West Shore Blvd | needs_contact | [record](https://aca-prod.accela.com/TAMPA/Cap/CapDetail.aspx?Module=Building&TabName=Building&capID1=26CAP&capID2=00000&capID3=01W3M&agencyCode=TAMPA) |
| `BLD-26-0526064` | 2026-06-23 | early_start | Airport / Westshore | office | **48** | Renovation-Interior/Exterior | 4915 Independence Pkwy | no_entity, needs_contact | [record](https://aca-prod.accela.com/TAMPA/Cap/CapDetail.aspx?Module=Building&TabName=Building&capID1=26CAP&capID2=00000&capID3=01TR2&agencyCode=TAMPA) |
| `BLD-26-0526061` | 2026-06-22 | early_start | Water Street | restaurant | **73** | Wagamama Pan Asian | 1050 Water St | needs_contact | [record](https://aca-prod.accela.com/TAMPA/Cap/CapDetail.aspx?Module=Building&TabName=Building&capID1=26CAP&capID2=00000&capID3=01TOI&agencyCode=TAMPA) |

## Filed in the last 90 days (13)

| Permit | Filed | Stage | Submarket | Trade | Tenant / project | Address | Flags | Source |
|---|---|---|---|---|---|---|---|---|
| `BLD-26-0526740` | 2026-07-21 | issued | Water Street | other | Sea Lion and Penguin Exhibits | 701 Channelside Dr | trade_other, already_awarded, needs_contact | [record](https://aca-prod.accela.com/TAMPA/Cap/CapDetail.aspx?Module=Building&TabName=Building&capID1=26CAP&capID2=00000&capID3=02069&agencyCode=TAMPA) |
| `BLD-26-0526643` | 2026-07-16 | issued | Airport / Westshore | office | Interior Alteration - 2nd Floor Common Areas | 4300 W Cypress St | already_awarded, no_entity, needs_contact | [record](https://aca-prod.accela.com/TAMPA/Cap/CapDetail.aspx?Module=Building&TabName=Building&capID1=26CAP&capID2=00000&capID3=01Z75&agencyCode=TAMPA) |
| `BLD-26-0526514` | 2026-07-11 | issued | Airport / Westshore | office | Interior Remodel 7th floor MEPs and Fire | 5426 Bay Center Dr | already_awarded, no_entity, needs_contact | [record](https://aca-prod.accela.com/TAMPA/Cap/CapDetail.aspx?Module=Building&TabName=Building&capID1=26CAP&capID2=00000&capID3=01XT2&agencyCode=TAMPA) |
| `BLD-26-0526501` | 2026-07-10 | issued | Downtown Riverwalk | office | AIC Architecture | 1000 N Ashley Dr | already_awarded, needs_contact | [record](https://aca-prod.accela.com/TAMPA/Cap/CapDetail.aspx?Module=Building&TabName=Building&capID1=26CAP&capID2=00000&capID3=01XP9&agencyCode=TAMPA) |
| `BLD-26-0526479` | 2026-07-09 | issued | Dale Mabry | office | Norlee Group | 2002 N Lois Ave | already_awarded, needs_contact | [record](https://aca-prod.accela.com/TAMPA/Cap/CapDetail.aspx?Module=Building&TabName=Building&capID1=26CAP&capID2=00000&capID3=01XDR&agencyCode=TAMPA) |
| `BLD-26-0526342` | 2026-07-06 | early_start | Airport / Westshore | retail | Edikted | 2223 N West Shore Blvd | needs_contact | [record](https://aca-prod.accela.com/TAMPA/Cap/CapDetail.aspx?Module=Building&TabName=Building&capID1=26CAP&capID2=00000&capID3=01W3M&agencyCode=TAMPA) |
| `BLD-26-0526369` | 2026-07-06 | revision | Downtown Riverwalk | office | Altieri Ins. Consultants | 400 N Tampa St #FS | needs_contact | [record](https://aca-prod.accela.com/TAMPA/Cap/CapDetail.aspx?Module=Building&TabName=Building&capID1=26CAP&capID2=00000&capID3=01WDJ&agencyCode=TAMPA) |
| `BLD-26-0526311` | 2026-07-02 | issued | Dale Mabry | office | Tampa Police Aviation Office | 4400 W Tampa Bay Blvd | blocklist:tampa police, already_awarded, needs_contact | [record](https://aca-prod.accela.com/TAMPA/Cap/CapDetail.aspx?Module=Building&TabName=Building&capID1=26CAP&capID2=00000&capID3=01VXW&agencyCode=TAMPA) |
| `BLD-26-0526100` | 2026-06-24 | issued | Airport / Westshore | office | CFS Staffing | 4200 W Cypress St | already_awarded, needs_contact | [record](https://aca-prod.accela.com/TAMPA/Cap/CapDetail.aspx?Module=Building&TabName=Building&capID1=26CAP&capID2=00000&capID3=01U6Y&agencyCode=TAMPA) |
| `BLD-26-0526064` | 2026-06-23 | early_start | Airport / Westshore | office | Renovation-Interior/Exterior | 4915 Independence Pkwy | no_entity, needs_contact | [record](https://aca-prod.accela.com/TAMPA/Cap/CapDetail.aspx?Module=Building&TabName=Building&capID1=26CAP&capID2=00000&capID3=01TR2&agencyCode=TAMPA) |
| `BLD-26-0526061` | 2026-06-22 | early_start | Water Street | restaurant | Wagamama Pan Asian | 1050 Water St | needs_contact | [record](https://aca-prod.accela.com/TAMPA/Cap/CapDetail.aspx?Module=Building&TabName=Building&capID1=26CAP&capID2=00000&capID3=01TOI&agencyCode=TAMPA) |
| `BLD-26-0525929` | 2026-06-17 | issued | Dale Mabry | office | Fly USA | 4300 W Tampa Bay Blvd | already_awarded, needs_contact | [record](https://aca-prod.accela.com/TAMPA/Cap/CapDetail.aspx?Module=Building&TabName=Building&capID1=26CAP&capID2=00000&capID3=01STC&agencyCode=TAMPA) |
| `BLD-26-0525940` | 2026-06-17 | revision | Airport / Westshore | office | Nationwide | 4200 W Cypress St | needs_contact | [record](https://aca-prod.accela.com/TAMPA/Cap/CapDetail.aspx?Module=Building&TabName=Building&capID1=26CAP&capID2=00000&capID3=01SVA&agencyCode=TAMPA) |

## Source notes

- Layer total 2577 features; record types present: Commercial Building Alterations (Renovations), Commercial Demolition Permit, Commercial New Construction and Additions
- 13 commercial records fell outside every tracked submarket
- 3 records were dropped as dwelling occupancies (R-2/R-3) — condo kitchen and bathroom remodels pulled under a commercial permit because the building is a threshold high-rise
- `source_url` is the City of Tampa Accela record page for that permit
