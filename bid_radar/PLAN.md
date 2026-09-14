# Bid Radar — Lead Engine Plan

**Goal.** A live tool that feeds Ideal Construction qualified GC opportunities in
Tampa's eight tracked submarkets: tenant fitouts identified early enough to
introduce the company and bid, plus the direct paths to master developers and
their GCs. Written 2026-09-14 for execution by a Claude Opus 5 session at
maximum effort. Everything marked **VERIFIED** was checked while writing this;
everything marked **DISCOVER** is a fact the executor must establish from the
source before building on it.

---

## 0. Hard constraints (read first)

1. **Sandbox egress.** The Claude remote environment for this repo blocks every
   data-source domain — VERIFIED 2026-09-14 by CONNECT test:
   `arcgis.tampagov.net`, `www2.myfloridalicense.com`, `dos.fl.gov`,
   `pubrec6.hillsclerk.com`, `www.tampaairport.com`, `compass.bespokemetrics.com`,
   `gasworx.com`, `www.tgh.org`, `api.jobtread.com`, `procurement.opengov.com`,
   `hcpafl.org`, `app.buildingconnected.com`. GitHub is reachable.
   **Therefore:** collectors run and are validated in **GitHub Actions**
   (`workflow_dispatch`, then read logs with `mcp__github__actions_run_trigger`
   / `mcp__github__get_job_logs`). Do not spend time on `curl` from the sandbox.
   JobTread is written through the **`mcp__Ideal__query`** connector (the
   JobTread Pave API — VERIFIED, org id `22P6bRn5p6Pn` in
   `ideal_apis/config/pipeline.yaml`); the tracker's database is written through
   the **Artifact tool** (`write_db`). Both bypass the sandbox egress.
   **Re-verified 2026-09-14** at the start of execution: `curl` to
   `arcgis.tampagov.net` fails (exit 56, no response), and `WebFetch` returns
   `EGRESS_BLOCKED` for the same host — the server-side fetcher goes through
   the same proxy, so it is not a way around this. `pypi.org` and `github.com`
   *are* reachable. **Actions is confirmed as the only path to the data.**
   *Fastest unblock:* the user widens the environment's network allowlist with
   the domains above. Until then, the Actions path is the path.
2. **No fabrication.** Every row the engine emits carries `source_url` and
   `retrieved_at`. Never invent a tenant, lease, contact or value. The files
   `permit_scraper/output_all_permits.csv` and `output_matches.csv` read as
   demo data (round values, 100% matches, `demo_test.py` alongside) — they are
   **not evidence the scrapers run**. Prove it in Actions.
3. **Never clobber human edits.** The tracker has two collections: `signals/`
   (machine-owned, idempotent upsert) and `opportunities/` (human-owned). The
   feed never writes to `opportunities/`; a human promotes a signal. The
   database is last-writer-wins with no transactions and a 5,000-document cap.
4. **Keep PRs small and validated.** One phase per PR. Base on
   `claude/bid-tracker-next-phase-0tiicz` while PR #28 is open, else `main`.
   Push to `claude/bid-radar-lead-engine-<phase>`.

---

## 1. What exists (reuse, do not rebuild)

| Asset | Path | State |
|---|---|---|
| Tracker UI (pipeline board, calibration, signals table, shared db) | `bid_radar/tampa-bid-radar.html` | Live artifact `https://claude.ai/code/artifact/a8a2e418-22fa-497d-af80-7bbfc8c34b2a`, capabilities `db` + `downloads` |
| Tampa permits scraper — public ArcGIS FeatureServer, no auth | `permit_scraper/scrapers/arcgis_api.py`, target `city_tampa` in `targets/counties.yaml` | **DISCOVERED: not reusable.** Every field it looks for (`PERMITTYPE`, `APPLICATIONDATE`, `APPLICANTNAME`, `ESTIMATEDVALUE`) is absent from the live layer, so `_normalise` would return rows with an empty permit type, no date and no applicant. The service URL and layer id in `counties.yaml` are correct and are the only parts kept. `bid_radar/collect.py` maps the layer directly. |
| Hillsborough (Accela/HillsGovHub), Pinellas, Pasco scrapers | `permit_scraper/scrapers/accela.py` | Written; `use_ai_agent: true` on Hillsborough |
| `RawPermit` dataclass (has lat/lon, value, sqft, filed/issued, parties) | `permit_scraper/scrapers/base.py` | Reuse as-is |
| SQLite `permits` table, unique on `(source_id, county_id)` | `permit_scraper/storage/models.py` | Reuse |
| Fuzzy **company** matcher (Publix/Amazon watch list) | `permit_scraper/agents/classifier.py` | Wrong tool for fitouts — not extended. `bid_radar/classify.py` written instead, keyed on the filed FBC occupancy category |
| Lead model, dedupe ledger, approval batches, JobTread push, QUO queue | `ideal_apis/ideal_apis/pipeline/{models,ledger,approvals,apply,jobtread_export}.py` | Reuse; extend `Source` literal |
| Daily cron pattern (7am ET weekdays, py3.12, upload-artifact) | `.github/workflows/daily-leads.yml` | Clone for `bid-radar-collect.yml` |
| Property appraiser adapters | `permit_scraper/scrapers/property_appraiser.py` | DISCOVER whether Hillsborough (HCPA) is covered |

---

## 2. Definitions the whole system hangs on

### 2.1 Submarkets (8) — `bid_radar/submarkets.geojson`
Built by `bid_radar/build_submarkets.py` from core rings drawn on street and
water boundaries, then grown by a trade-area buffer. Looked up at runtime by
`bid_radar/geo.py` (ray casting, no third-party dependency).

**Buffer is not uniform — DISCOVERED, PLAN originally said 0.5 mi for all.**
A half-mile buffer on contiguous downtown districts makes each swallow its
neighbours, and on Davis Islands it crosses Seddon Channel and takes Water
Street's permits. So:

| Buffer | Applies to | Why |
|---|---|---|
| 0.50 mi | wsmarina, dalemabry, airport | Isolated districts; a tenant two blocks out is still that district's lead |
| 0.25 mi | davis | Isolated, but 0.5 mi crosses the channel into Water Street |
| 0.10 mi | riverwalk, downtown, waterst, ybor | Already share boundaries; 0.10 mi is a half-block tolerance for addresses geocoded to a street centreline |

**`ybor` is not a rectangle.** The historic district stops at Adamo Dr; the
Gasworx corridor runs south from there to Channelside Dr between 14th St and
the Ybor Channel; Ybor Harbor is the waterfront east of that. A rectangle
reaches across Adamo and captures the Channel District.

**Polygons overlap; `PRECEDENCE` in `build_submarkets.py` resolves it**, most
specific first: `waterst, davis, ybor, riverwalk, downtown, wsmarina,
dalemabry, airport`. `waterst` is tested before `davis` so that Amalie Arena
and 1050 Water St do not fall into the Davis Islands trade area. `riverwalk`
and `downtown` deliberately overlap along Ashley Dr — the tracker itself files
The Pendry (100 N Ashley) under "Downtown Riverwalk" and 601 N Ashley under
"Downtown Tampa", two labels for one place. Permits on that frontage resolve
to `riverwalk`; both are tracked, so no lead is lost either way.

**Acceptance test — CHANGED from the plan.** PLAN called for geocoding the 15
tracker projects and asserting containment. That test is run
(`tests/test_submarkets.py::test_tracker_projects_fall_inside_their_assigned_submarket`,
fixture `tests/fixtures/projects.geojson`, each row carrying its locator, its
source and whether the locator is a published street address or a district
anchor) — but it is the *weaker* of the two, because six of the fifteen are
district-scale projects with no single street address, so testing them against
a polygon drawn for that district is close to circular.

The substantive test is
`test_real_permit_points_resolve_to_the_right_submarket`: 15 **real permit
coordinates served by the ArcGIS layer itself** (`tests/fixtures/permit_points.geojson`),
asserting both that in-submarket permits resolve correctly *and* that
out-of-submarket ones return `None`. Those coordinates are not geocoded or
estimated, and they caught three polygon errors that the project fixture did
not (Ybor eating the Channel District; Davis Islands eating Water Street;
Water Street losing Amalie Arena).

| id | Hood (as in tracker) | Anchor |
|---|---|---|
| ybor | Ybor City | Gasworx, Live Nation, Ybor Harbor |
| riverwalk | Downtown Riverwalk | The Pendry |
| downtown | Downtown Tampa | Manor, ONE Tampa, Ora, 601 N Ashley |
| davis | Davis Islands | TGH Taneja Tower |
| waterst | Water Street | Phase Two, Entertainment District |
| wsmarina | Westshore Marina | AQUA, Marina Pointe |
| dalemabry | Dale Mabry | Rays stadium district (Hillsborough College site) |
| airport | Airport / Westshore | TPA expansion, Westshore business district |

### 2.2 Signal → `RawSignal`
```
id            stable hash of (source, source_id)            dedupe key
source        permit | abt | dbpr_hr | sunbiz | ahca | noc | hcaa_ppo | manual
hood          one of the 8 ids, or null if outside all polygons (dropped)
address, lat, lon, parcel
entity        applicant / licensee / LLC name as filed
              — for permits this is PARSED out of PROJECTNAME2 /
                PROJECTDESCRIPTION (classify.entity_of); the layer has no
                applicant, owner or contractor field. Null where it could not
                be read with confidence — never a guess.
brand         normalized brand if recognizable, else null
trade         medical | restaurant | retail | office | hospitality | other
stage_hint    early_start | issued | revision      (permit source)
              — DISCOVERED: there is no `applied` stage. See §2.3(d).
value_est     $ from permit valuation, or null
              — NEVER available from the Tampa permit layer: no valuation field
sqft          from permit, or null
seats         from DBPR H&R licence, or null
filed_at      the source's own date
bid_window    {open, close} inferred per §2.4
contacts[]    {kind: phone|email|agent, value, from}   — only from public records
              — empty for every permit row; the layer has no contact field.
                Tampa's AlcoholBeverage layer DOES carry them (§3 #3a).
source_url, retrieved_at
confidence    0–1 from classifier (0.9 when trade came from the filed FBC
              occupancy category, 0.5 from keywords, 0.2 unclassified)

Added by the permit collector beyond the original schema:
occupancy_category   the FBC category the applicant filed under — the single
                     most useful field in the layer, and the basis of `trade`
is_fitout            fitout-capable record type AND not a dwelling occupancy
is_dwelling          R-2/R-3* — a condo remodel under a threshold-building
                     permit, not a job any GC bids
scope                readable scope with Tampa's admin prefixes stripped,
                     shown where `entity` is null
record_type          RECORDTYPE verbatim
city_neighborhood, cra, council_district   Tampa's own geography, kept as a
                     cross-check on our polygons
```

### 2.3 Qualified lead — ALL of:
- (a) `hood` non-null;
- (b) `trade` ≠ other;
- (c) `value_est ≥ 75,000` or `sqft ≥ 1,200` or `seats ≥ 30`, **or** the signal
  is a licence-type source (abt/ahca/dbpr_hr) where value is unknowable;
  **DISCOVERED: permit rows fall in the second branch too** — the Tampa layer
  publishes no valuation, and `NEWCONSTRUCTIONSF` is 0 on every alteration.
  Seats and sales-area SF *are* available, from the ABT layer (§3 #3a);
- (d) bid window opens within 9 months. **REWRITTEN — the plan assumed an
  `applied` stage that does not exist.** `PROJECTSTATUS` on the Tampa layer
  only ever reads `Issued` or `Revision`: the layer publishes at issuance and
  has no application or in-review state, so it cannot be queried for permits
  still in review. What it does carry:
    - `early_start` — the city has released interior non-structural work while
      the main permit is still pending ("No inspections may be scheduled until
      the permit is issued"). **This is the only permit row with a live bid
      window**, and it is the row to act on. 6 of 29 commercial records in the
      last 90 days were EARLY START.
    - `revision` — a change to an in-flight permit; the job is active.
    - `issued` — already awarded. Keep, tag `late`, route to §4 win-rate
      analysis, not outreach.
  Intake→issue lag (CREATEDDATE→LASTUPDATE) ran 15–66 days, median 35, across
  the 25 most recent commercial records. So a permit that appears today was
  applied for about five weeks ago — and the *real* leading indicators have to
  come from the licence and entitlement layers, not from permits;
- (e) an identifiable entity with ≥ 1 public contact channel — **no permit row
  can satisfy this on its own**; the contact has to come from the ABT layer
  (§3 #3a), Sunbiz, or HCPA ownership. Match on address;
- (f) not matched to a JobTread account with a lost/declined outcome;
- (g) not on the national-in-house-GC blocklist (`bid_radar/blocklist.yaml`,
  start with the obvious: Publix, Walmart, Amazon, Starbucks corporate,
  Chipotle, banks' branch programs).

### 2.4 Score (0–100), qualified at ≥ 55
- **Fit** (max 30): medical 30 · restaurant 25 · hospitality 20 · retail 15 · office 10
- **Urgency** (max 30): bid opens ≤ 30 d → 30 · ≤ 90 d → 22 · ≤ 180 d → 12 · later → 5
- **Value** (max 20): `min(20, 4·log10(value_est/10,000))`; unknown → 8
- **Access** (±20): public contact +10 · owner-occupier or local LLC +10 ·
  national brand with in-house GC −20 · GC already named on the record −15
- Bid-window inference: permit applied → opens now, closes +60 d;
  ABT / DBPR H&R filed → opens +30 d, closes +180 d; Sunbiz LLC at a
  commercial address → opens +90 d, closes +365 d; AHCA application →
  opens +60 d, closes +270 d.

---

## 3. Data sources — OBSERVED state (rewritten 2026-09-14 after discovery)

Everything below marked OBSERVED was established by querying the source from
GitHub Actions on 2026-09-14. Raw output is committed to the `bid-radar-data`
branch under `bid_radar/data/vocab_*.json`.

### The headline finding

PLAN assumed one Tampa permit source and reached for DBPR/Sunbiz files for the
leading indicators. In fact **Tampa's own ArcGIS `Planning` folder carries
four layers we can use**, all public, no auth, point geometry, one host that
Actions can already reach — and two of them are *earlier* and *richer* than
what PLAN planned to scrape from the state:

| Layer | n | What it gives that permits cannot |
|---|---|---|
| `PermitsAll` | 2,577 | The job itself — but only at issuance |
| `ActiveEntitlementLocations` | 289 | **Live rezoning / special-use cases, 100% still pending**, with hearing dates. The 9–18 month signal. |
| `AlcoholBeverage` | 4,096 | **Business name, owner name, phone and email.** The only source of a contact channel. |
| `CRACommercialInitiative` | 38 | Funded interior fitouts with a named applicant and an award amount |

### 1. City of Tampa permits — OBSERVED

`arcgis.tampagov.net/arcgis/rest/services/Planning/PermitsAll/FeatureServer/0`

Everything `permit_scraper/scrapers/arcgis_api.py` assumes about this layer is
wrong: there is no `PERMITTYPE`, no `APPLICATIONDATE`, no `APPLICANTNAME`, no
valuation field. Do not use that scraper for this source — `bid_radar/collect.py`
maps the layer directly.

- **Point geometry**, native SR 102100; request `outSR=4326`. `maxRecordCount`
  2000, pagination supported.
- **2,577 features total**, a curated set: `RECORDTYPE` has exactly 7 values
  (residential/commercial × new construction / alterations / demolition). No
  electrical, plumbing, mechanical, roofing or sign sub-permits.
- **`PROJECTSTATUS` has exactly two values: `Issued` (1,770) and `Revision`
  (807).** No application stage — see §2.3(d).
- Dates: `CREATEDDATE` (intake) min 2006-11-21, and `LASTUPDATE` (issue /
  last touch). 158 records created in the last 90 days, of which **29 are
  commercial**: 19 Commercial Alterations issued, 4 Commercial Alterations
  revision, 4 Commercial Demolition, 2 Commercial New Construction.
- **`OCCUPANCYCATEGORY` is the find** — the FBC occupancy the applicant filed
  under (42 distinct values: `A-2 Assembly-Food & Drink. Restaurant. Night
  Club. Bar`, `B-5 Business-Clinic. Outpatient`, `M-4 Mercantile-Retail`, …).
  It gives `trade` directly, far better than keywords. Mapped in
  `bid_radar/classify.py::OCCUPANCY_TRADE`; a test asserts every code seen in
  the live vocabulary is mapped.
- **`URL` is a per-permit Accela deep link** (25 distinct across 25 sampled
  records) — a genuine `source_url`.
- No applicant/owner/contractor field; the tenant is parsed from
  `PROJECTNAME2` / `PROJECTDESCRIPTION` (`classify.entity_of`, 17 of 29 rows
  resolved on the first real run).
- Trap: commercial record types include condo kitchen and bathroom remodels in
  threshold high-rises. Filter on `OCCUPANCYCATEGORY` R-2/R-3* — see
  `classify.is_dwelling`.

### 2. Hillsborough permits — unchanged, still deprioritized

HillsGovHub Accela `aca-prod.accela.com/HCFL`, browser scrape. All eight
tracked submarkets are inside city limits, so this adds little. Not attempted.

### 3. City of Tampa alcoholic-beverage permits — OBSERVED, REPLACES the DBPR CSV

`arcgis.tampagov.net/arcgis/rest/services/Planning/AlcoholBeverage/FeatureServer/0`

4,096 points. **This is the only source in the whole system that carries a
contact channel**, which §2.3(e) requires:

| Field | Filled | of 4,096 |
|---|---|---|
| `BUS_NAME` | 3,094 | 76% |
| `BUS_OWNER_NAME` | 2,486 | 61% |
| `BUS_PHONE` | 1,939 | 47% |
| `BUS_OWN_EMAIL` | 890 | 22% |
| `BUS_OWN_PHONE` | 453 | 11% |
| `AB_SLS_AREA_TTL_SF` | 4,087 | 99.7% |
| `SEAT_COUNT` | 23 | **0.6% — unusable**; drop `seats` from scoring |

- `HISTORY_ACTION`: `Active` 1,634 · `Dry` 1,515 (closed) · the rest are change
  records. Filter to `Active` for live venues; a transition *to* `Active` is
  the opening signal.
- Class: `AB_CLASS_PREFIX` 2/4 = 2COP/4COP; `ABSALECONDITION` distinguishes
  `Consumption On Premises-Restaurant` (1,134) from `Package Sales` (994) —
  the former is a buildout, the latter usually is not.
- Volume: `CREATEDATE` carries 30 new records in the last 365 days;
  `LASTUPDATE` touched 274. So ~30 genuinely new wet-zoning records a year
  citywide, plus status changes on existing ones.
- **Trap: bad dates.** `ORD_LTR_DT` has a max of `2997-01-29` and `FIRE_PMT_DT`
  a min of `0201-04-11`. Any collector must clamp to a sane range.
- **Consequence: PLAN §3 old-#3 (DBPR ABT daily CSV) and old-#4 (DBPR H&R) are
  now second priority.** Tampa's own layer is geocoded, contact-bearing and on
  a host we have already proven reachable. Use DBPR only to cover seats and
  food-service licences the city layer misses.

### 4. City of Tampa active entitlements — OBSERVED, NEW, the earliest signal

`arcgis.tampagov.net/arcgis/rest/services/Planning/ActiveEntitlementLocations/FeatureServer/0`

289 points, **every one of them a live case**: `APPSTATUS` is `In Process`
(218), `Awaiting Client Reply` (53) or `Open` (18). 272 created in the last
365 days. 100% fill on `RECORDID`, `ADDRESS`, `TENTATIVEHEARING` and `URL`
(Accela deep link).

`RECORDALIAS`: Rezoning 79 · Variance Review Board 58 · Design Exception 40 ·
Formal Decision 30 · ROW Vacating 26 · General Land Use 24 · Special Use 16 ·
**AB Special Use 13** (alcoholic-beverage special use — an F&B tell).

This is the 9–18-month signal PLAN had no source for, and it comes with a
dated hearing to work backwards from. **Build this collector first in Phase 2.**

### 5. CRA Commercial Initiative grants — OBSERVED, NEW

`arcgis.tampagov.net/arcgis/rest/services/Planning/CRACommercialInitiative/MapServer/0`

38 records, 100% fill on `APPLICANT`, `BUSINESSPROPERTYOWNER`, `ADDRESS` and
`DESCRIPTION`; `AWARDEDAMOUNT` on 37, `TOTALPROJECTCOST` on 30 — so this is
the one permit-adjacent source that yields a real `value_est`. Grant types
include `Commercial Interior Grant` (6), `Commercial Design Grant` (2) and
`Vanilla Shell Grant` (1). `OCCUPANCY` splits Occupied 19 / Vacant 19.

Only 8 of the 38 fall in a CRA that overlaps our submarkets (Ybor City 1/2,
Downtown Core/Non Core) — small, but every one is a funded fitout with a named
applicant. Cheap to collect.

### 6. Sunbiz, AHCA, Clerk NOCs, HCAA PPO — ALL FOUR OBSERVED 2026-09-14

Three discovery rounds (`discover_state.py`, `_state2.py`, `_state3.py`) ran
these from a GitHub runner. PLAN's guesses about all four were wrong in ways
that mattered.

| # | Source | Status | What was actually found |
|---|---|---|---|
| 6a | **Sunbiz** daily corporate filings | **BUILT, DORMANT** — `sources/sunbiz.py` | Not a free download. The files are served from `sftp.floridados.gov`, which returns **401** to an anonymous runner; `dos.myflorida.com/sunbiz/data/cor/` 404s and `search.sunbiz.org/data/cor/` 403s. There is no anonymous mirror. The collector is written and gated on `SUNBIZ_USER`/`SUNBIZ_PASS`; it returns empty and says why until those exist. |
| 6b | **AHCA** health-care licensure | **OPEN — no route found** | Per-county extracts exist only for Miami-Dade (`AllFacilityData_MiamiDade_*.xlsx`, 726 KB, HTTP 200); the equivalent Hillsborough path 404s. The facility search posts to `/Facility-Search/FacilityLocateSearch`, which returns **400** to `County`, to its own control name `countySelection`, and to a full field set — it is a client-rendered app with no hidden form fields (`hidden_fields: []`). Remaining route is Playwright against the UI, which is brittle. **Not built, deliberately.** |
| 6c | ~~**Hillsborough Clerk** ORI~~ | **CLOSED — see §3 #10** | Both public-records hosts refuse cloud traffic: `ConnectTimeout` on `pubrec6.hillsclerk.com`, `ConnectionError` on `pubrec.hillsclerk.com`, while `www.hillsclerk.com` answers 200 from the same runner. Not the network — those hosts. Replaced by #10, which is better. |
| 6d | **HCAA** Planned Procurement monthly PDF | **BUILT** — `sources/hcaa_ppo.py` | URL pattern confirmed over seven consecutive months, ~180 KB each. The OpenGov portal is NOT an alternative: the portal 403s and both `/api/public/…` endpoints return 50,872 bytes of `text/html` — identical size, i.e. the SPA shell, not JSON. |
| 6e | **Geocoding** | **BUILT** — `geocode.py` | PLAN said "not needed for sources 1, 3, 4, 5", which was right and is now insufficient: 6a and the DBPR files carry a street address and no geometry. See §3 #9. |
| 6f | **DBPR Hotels & Restaurants** | **BUILT** — `sources/dbpr_hr.py` | PLAN pointed at the ABT daily file, which §3 #3 already replaced. The files that matter were never named in PLAN — see §3 #8. |

### 8. DBPR Hotels & Restaurants extracts — OBSERVED, NEW

`https://www2.myfloridalicense.com/sto/file_download/extracts/`

PLAN's entry for DBPR pointed at the alcoholic-beverage daily file, which the
Tampa ArcGIS layer already replaced (§3 #3). The valuable files are different
ones, and the landing pages link 300 of them:

| File | Rows | What it is |
|---|---|---|
| `newfood.csv` | 1,274 | **New food-service licences**, current fiscal year |
| `chgownr_food.csv` | 1,141 | **Change of ownership** — in this trade, almost always a remodel |
| `newlodg.csv` | 2,356 | New lodging licences |
| `chgownr_lodg.csv` | 290 | Lodging change of ownership |
| `hrfood{1..7}.csv` | 7,943–15,072 | The full licence list, one file per inspection district. **District 3 is Hillsborough** (4,710 rows; the other six have 0–8). Not needed — the `new*` files are statewide and small. |

38 columns including `Location Street Address`, `Location County`,
`Business Name` (the trading name), `Licensee Name` (the holding company),
`Primary Phone Number`, `Number of Seats` and `License Number`.

**Three traps, each seen in the real files:**

1. **The column order is not the same across files.** All four ship the same
   38-name header, but `newfood.csv` has the phone at index 15 and the county
   code at 16 while `chgownr_food.csv` has them reversed — a real row there
   reads `Primary Phone Number = "39"` and `Mailing County Code =
   "8134886294"`. Mapping by header name alone gets the phone wrong in one
   file out of two.
2. **`newlodg.csv` ships a different, shorter header** — 34 columns, no
   `Location County` at all. There is no single schema.
3. **A Tampa mailing address is not a Tampa job.** The first row of
   `newfood.csv` is BLUSH SOCIAL, mailing Tampa 33647, building at
   101 Philippe Pkwy, Safety Harbor — Pinellas. Only the `Location …` fields
   decide.

**And one the first live run found:** `Rank Code` `MFDV` is a mobile food
dispensing vehicle — a food truck — and `VEND` a vending machine operator.
Nine of the first 23 qualified rows were one or the other, five of them
sharing 4601 N Lois Ave, a commissary where trucks register. One kitchen, not
five fitouts. Both are `not_fitout` now.

`Number of Seats` is filled on these rows, which is the build-size proxy the
ABT layer could not give (23 of 4,096 there).

### 9. US Census geocoder — OBSERVED, NEW, and now required

`https://geocoding.geo.census.gov/geocoder/locations/addressbatch` — free, no
key, batch CSV in and out. It answered a runner on 2026-09-14.

It was not trusted on a 200. It was checked against four Tampa addresses whose
submarket the ArcGIS geometry already knew:

| Address | Census → | ArcGIS said | |
|---|---|---|---|
| 1616 E 7th Ave | ybor | ybor | agreed |
| 253 N West Shore Blvd | airport | airport | agreed |
| 12908 N Dale Mabry Hwy | outside | outside | agreed |
| **1050 Water St** | **"Tie"** | waterst | **no coordinates returned** |

That last row is the limit of this source and the reason nothing guesses.
Water Street is new construction and the TIGER road file has not caught up. An
unresolved row keeps `hood: None` and `needs_geocode: True`; it is never
placed by ZIP, because 33602 alone spans Downtown, the Riverwalk, Water Street
and the Channel District. Misses are cached alongside hits, so a bad address
is not re-sent every run.

### 10. City of Tampa Accela record pages — OBSERVED, the richest source we have

`aca-prod.accela.com/TAMPA/Cap/CapDetail.aspx?...` — the URL the ArcGIS permit
layer already puts on every row.

This was found while looking for a replacement for the Clerk, and it turns out
to answer far more than the win-rate question. One record page carries every
field the ArcGIS layer omits:

| On the page | What it gives us |
|---|---|
| **Licensed Professional** | The **GC of record** — company, Florida licence number, email. This IS the win-rate dataset |
| **Applicant** | Name, work phone, email |
| **Owner** | Name and mailing address |
| **Tenant contact** | Where the record has one |
| **Job Value** | The valuation §2.2 said was never available |
| **Sq Ft** | The real floor area (`NEWCONSTRUCTIONSF` is 0 on every alteration) |
| Additional Licensed Professionals | Each sub's company and licence |

**Verified 2026-09-14 on BLD-26-0526061** (Wagamama, 1050 Water St): GC *TWT
Restaurant Design Construction & Development Company*, licence CBC1262713,
`permits@twtconstruction.com`; applicant Stephen Torres, 9728079257,
`storres@weareharrison.com`; owner *Wst 1010 Water Street Llc c/o Strategic
Property Partners Llc*; tenant contact Philip Hart; Job Value 300,000; Sq Ft
4,525; subs Duffy Electric and Johnson Controls Fire Protection.

- 200 OK from a GitHub runner; ~370 KB per page, ASP.NET with viewstate.
- **Parse the printed labels, not the DOM.** `bid_radar/accela.py` flattens the
  page to text and anchors on `Applicant:`, `Licensed Professional:`, `Owner:`,
  `Job Value:`, `Sq Ft:`. The DOM is generated and brittle; those labels are
  not.
- Cost: one fetch per permit. `bid_radar/enrich.py` caches parsed results by
  record id in `data/accela_cache.json` on the data branch, so a second run
  fetches only new records, and `ACCELA_MAX_FETCH` caps a single run. The cache
  is flushed every `ACCELA_SAVE_EVERY` (20) fetches — the first live run was
  cancelled at nine minutes by an unrelated push (`cancel-in-progress: true`)
  and lost everything it had paid for.
- **Accela's speed is not dependable, and this is the main operational risk.**
  The same 223 pages took ten minutes on the 2026-09-14 02:22Z run and were
  still going at forty-four minutes on the 02:42Z one, with a warmer cache and
  no change on our side. `ACCELA_BUDGET_S` (600s) stops the fetching; the run
  uses what is cached, counts what it skipped, and finishes. A slow day costs a
  partial back-catalogue, never a dead job, and the next run tops the cache up.
- **Four parsing defects the first live run exposed, now fixed and tested**
  (`tests/test_accela.py`). They mattered because each one would have gone
  straight onto a cold call:
  | Seen in `market_share.csv` | Cause | Fix |
  |---|---|---|
  | `N HOWARD AVE TAMPA` as a company | the party block runs name → address → licence, and the address matched the firm pattern | truncate the block at the first street number; reject any candidate carrying a street word |
  | `MATTHEW GILBERT BARR & BARR INC` | a person and their firm on one line | `_split_person_from_firm()` — greedy firm match, the remainder is the person |
  | Job Value `280,000,000` on a fitout | data entry on the record | kept on the row, `value_suspect: true`, excluded from market-share averages |
  | Job Value `500` | same | same |
- **Consequence for §2.2 and §2.3:** `value_est` and `contacts[]` ARE available
  for permits after enrichment. The soft `needs_contact` blocker still exists
  for rows Accela could not fill, but it is no longer true that no permit row
  can carry a contact.

**Not to build:** Hillsborough BTR (late, low value), CoStar (paid), Related
Group prequal (none public — tenant-side only), Hillsborough Clerk ORI (its
hosts refuse cloud traffic, and Accela names the same contractor with a licence
number attached).

## 4. Direct paths to master developers and their GCs — VERIFIED 2026-09-14

These are relationship rows, not data rows. Seed them into `opportunities/` as
`trade: relationship` with a next action and owner so they get worked.

| Target | Fact | Action |
|---|---|---|
| **Moss** — GC for Water Street (Cora; entertainment venue JV with Barton Malow) *and* Gasworx (office + Olivette) | Prequalifies subs through **COMPASS** (`compass.bespokemetrics.com`), used by 60+ Florida GCs | Register on COMPASS once → opens Moss and every other FL GC on it. Highest-leverage single action on this list. |
| **AECOM Hunt / Turner** — CM for the Rays stadium district, named 2026-07-17 | Deal approved by Hillsborough **2026-08-28**; site prep Sept 2026, demolition Dec, foundations Mar 2027, Opening Day 2029; 113-acre mixed-use "Innovation Edge" at the Hillsborough College Dale Mabry site | Get on both firms' sub/prequal lists now; the district's retail/F&B fitouts follow the bowl. **Tracker row still to update in Phase 3** (currently names Hines/Populous only). Note the `dalemabry` polygon is drawn on this site and the collector is already returning permits there. |
| **KETTLER / Gasworx** | Retail leasing for four key blocks run by **JPRE Development** and **Archer Group Real Estate**; Ferguson signed ~50,000 SF office (Aug 2026) | Introduce to JPRE and Archer — they know the tenants a year before any record. Ferguson TI is a live corporate fitout: find the tenant-rep. |
| **SPP / Water Street** | No public prequal; `info@spprealestate.com`, 1001 Water St Ste 1250; new 452-unit residential tower announced July 2026 | Relationship letter + COMPASS (Moss) is the realistic route; tenant-side for the entertainment district |
| **Tampa General Hospital** | Formal vendor/supplier application and certification requirements at `tgh.org/vendor--supplier-information/` | Submit the application; ask for the construction-services category |
| **HCAA / Tampa International** | Prequalified Contractors List RFP (building construction, site work, paving) **closed 2026-09-03** — missed. Contact listed: Nick Diaz, `ndiaz@tampaairport.com`. Tenant Work Permit Handbook governs concession fitout contractors. | Email Diaz re: next prequal cycle; watch the monthly PPO report (source #8); register on OpenGov + DemandStar for HCAA |
| **Sunwest Construction** (Hotel Ora) | Regional, reachable, per tracker | Direct intro; strongest relationship target on the board |
| **BuildingConnected** (Autodesk) | Invites are driven by *Work Performed* scopes and *Service Area* on the profile | Complete profile: TI, medical office, restaurant, retail; Hillsborough / Pinellas / Pasco. Also keep the PlanHub profile current (`planhub_gc_scraper.py` already logs in there). |

---

## 5. Architecture

```
GitHub Actions (open egress)             Claude Routine (daily, fresh session)          Humans
─────────────────────────────            ──────────────────────────────────────          ──────
collect.py                               1. get_file_contents(bid-radar-data:            tracker page
  permits (Tampa ArcGIS, Hillsb.)           bid_radar/data/signals.jsonl)                 ├ New-signals tray
  abt.py  dbpr_hr.py  sunbiz.py          2. read_db list signals/ → diff                  │  Promote → opportunities/
  ahca.py  noc.py  hcaa_ppo.py           3. write_db batch (≤50/call):                    │  Dismiss → signals/{id}.dismissed
    → RawSignal                              new → set ; existing → update machine        ├ stage / value edits
    → geocode (Census→Smarty)                fields only (preserve dismissed/promotedTo)  ├ "Send to JobTread" (mcp: Ideal)
    → polygon filter (submarkets.geojson) 4. prune signals > 180 d, unpromoted           └ Won/Lost → calibration
    → FitoutClassifier → score            5. digest → Slack webhook / Gmail
    → signals.jsonl + summary.md
  commit to branch `bid-radar-data`      outcome writeback: JobTread job status →
                                         opportunities/{id}.stage (via mcp__Ideal__query)
```

- **Why commit to a data branch:** the Routine session can read GitHub but not
  the source sites; a branch is the simplest durable hand-off that keeps
  history. Use `bid-radar-data`, never `main`.
- **Why a Claude Routine and not an Action for the db write:** only a Claude
  session holds the Artifact tool. `create_trigger` with
  `create_new_session_on_fire: true`, cron `0 13 * * 1-5` (9am ET weekdays,
  after the 7am collector).
- **Idempotency:** `signals/{id}` where `id` = §2.2 hash. Re-runs are no-ops.
- **Human-owned fields on a signal** the feed must never overwrite:
  `dismissed`, `promotedTo`, `notes`.

---

## 6. Phases, in execution order, with acceptance criteria

### Phase 0 — Prove the feed (first PR) — ✅ DONE 2026-09-14
1. `bid_radar/submarkets.geojson` + fixture + test (§2.1).
2. `bid_radar/collect.py` — runs `ArcGISPermitScraper` for `city_tampa` with
   `days_back=90`; writes `data/vocab_tampa.json` (distinct values);
   applies a **first-pass** fitout filter derived from that vocabulary
   (commercial alteration / interior / tenant / build-out / remodel work
   classes — confirm the actual strings); polygon filter; writes
   `data/signals.jsonl` and `data/summary.md` (counts per hood × trade).
3. `.github/workflows/bid-radar-collect.yml` — clone of `daily-leads.yml`:
   `workflow_dispatch` + `0 12 * * 1-5`; installs `permit_scraper` +
   `bid_radar` deps; runs `collect.py`; commits `bid_radar/data/*` to branch
   `bid-radar-data` (create if absent) with `GITHUB_TOKEN`.
4. Trigger it from the session, read the logs, iterate until green.

**Done when:** the workflow is green; `summary.md` on `bid-radar-data` lists
real Tampa fitout permits from the last 90 days by submarket, each with permit
number, address, tenant and source URL; the fixture projects pass the polygon
test.

**What actually happened.** Green on run 4 (`workflow_dispatch` is not
available until the workflow file reaches the default branch, so `push` on
`claude/bid-radar-lead-engine-**` is the iteration trigger — that is a GitHub
constraint, not a choice). First real output: 29 commercial records in 90
days, 16 in a tracked submarket, 3 at EARLY START (Wagamama Pan Asian at 1050
Water St; Edikted at WestShore Plaza; a renovation at 4915 Independence Pkwy).
113 tests pass. Two deviations, both recorded above: the acceptance test is
anchored on 15 real ArcGIS permit coordinates rather than on geocoded project
addresses (§2.1), and the window is 365 days with the last 90 called out
separately, because 90 days of commercial permits is only 29 records citywide.

Deferred out of Phase 0, deliberately: `data/vocab_tampa.json` is written by
`discover_tampa.py` as PLAN asked, but the fitout filter is built on
`RECORDTYPE` + `OCCUPANCYCATEGORY` rather than on the `PERMITTYPE`/`WORKCLASS`
fields PLAN named, because those fields do not exist.

### Phase 1 — Classify, score, and shake hands with JobTread — ✅ DONE 2026-09-14

1. `bid_radar/classify.py` — trade from the filed FBC occupancy category
   (0.9 confidence), keywords as fallback (0.5), tenant name parsed from
   `PROJECTNAME2` / `PROJECTDESCRIPTION`. Two rules came out of hand-labelling
   the first real run and are worth keeping:
   - **Demolition guard.** A demolition record type returns `other` without
     consulting keywords. Without it, "demolition of two story wood framed
     office buildings" classified as `office` and put a teardown on the
     outreach list.
   - **Strip-out stage.** When the record says the space is being emptied and
     the build-back comes under a separate permit, the trade is not declared
     yet — but the tenant is committed and the fitout has not been bid. That
     is `stage_hint = strip_out`, scored on its own fit band (§2.4), and it is
     one of the more actionable rows the layer produces. Detection is
     deliberately conservative: it fires only when the record itself says the
     build-back is separate, because mistaking a real fitout for a strip-out
     loses the lead.
2. `bid_radar/score.py` + `blocklist.yaml` — §2.3 and §2.4. Two adaptations,
   both recorded in §2.3: value is unknowable from permits so it takes the
   plan's own 8/20 for unknown, and the contact-channel requirement is a SOFT
   blocker (`needs_contact`) rather than a hard gate, because enforcing it
   would qualify nothing at all until Phase 2.
   PLAN's Access "+10 owner-occupier or local LLC" is implemented as the proxy
   `named_local_entity`: an entity was resolved and it is not blocklisted.
   Labelled as a proxy, not as verified ownership, until Sunbiz/HCPA confirm it.
3. `bid_radar/to_leads.py` — qualified signals → `LeadRecord` → the existing
   `ApprovalBatch`, dry-run by default. Signals with contacts become contact
   leads (JobTread-eligible); signals without become **intel** leads, which is
   the slot the batch already has for non-contactable rows. Every permit signal
   is intel today. The only edit to `ideal_apis` is the `Source` literal.
4. JobTread handshake — **OBSERVED via `mcp__Ideal__query`, 2026-09-14.** Both
   shapes Phase 3's page code will need:

   ```
   REQ  {"currentGrant": {"organization": {"id": {}, "name": {}},
                          "user": {"id": {}, "name": {}}}}
   RES  {"currentGrant": {"organization": {"id": "22P6bRn5p6Pn",
                            "name": "Ideal Construction - CGC1537480 / MRSR5016"},
                          "user": {"id": "22NsRpDbCjaP", "name": "Ideal Construction"}}}

   REQ  {"organization": {"$": {"id": "22P6bRn5p6Pn"},
           "accounts": {"$": {"where": {"and": [["type","customer"],
                                                ["name","like","%Ramos%"]]}, "size": 5},
                        "count": {}, "nodes": {"id": {}, "name": {}}}}}
   RES  {"organization": {"accounts": {"count": 2, "nodes": [
           {"id":"22P6bShi6gag","name":"Ramos Design Companies"},
           {"id":"22P6c2J3bJT2","name":"Ramos Design Build Corporation 2"}]}}}
   ```

   `currentGrant.user` has **no** `email` field — asking for it errors. The org
   holds 259 `customer` accounts. `createAccount` takes
   `{organizationId, name, type, suffixIfNecessary, isTaxable, notify,
   customFieldValues}`; `suffixIfNecessary` appends a number to keep the name
   unique, which is what "Send to JobTread" should pass so a repeat push cannot
   collide. **No page code may call anything not shown above.**

**Done when:** precision ≥ 0.8 on the labelled sample for `trade`; scores are
written into `signals.jsonl`; permit-sourced leads carry `source_url`; one
dry-run JobTread push validated.

**What actually happened.** Precision is 29/29 on `tests/fixtures/labels.csv` —
which is every row of the first real run, hand-labelled, and also the set the
two rules above were derived from, so read it as a fit to the sample and expect
the held-out number from the next run. Scoring is wired into the collector.
The dry run reports 4 qualified of 29: Wagamama Pan Asian (73, restaurant,
early start, Water Street), Edikted (63, retail, early start, WestShore Plaza),
Altieri Ins. Consultants (58, office, revision, 400 N Tampa St) and Nationwide
(58, office, revision, 4200 W Cypress St). 214 tests.

**The number that matters: the permit feed alone yields about four qualified
leads a quarter, none with a contact channel.** That is not a threshold problem
— 19 of the 29 are already-issued permits, which §2.3(d) correctly refuses to
call outreach. It is the argument for Phase 2.

### Phase 2 — Leading indicators (REORDERED after discovery) — ✅ DONE 2026-09-14

The state-file collectors PLAN originally listed are no longer the first
things to build. Tampa publishes earlier, geocoded, contact-bearing versions
of two of them on a host we have already proven reachable (§3).

1. `entitlements.py` — `ActiveEntitlementLocations` (§3 #4). Highest value per
   line of code in the whole project: 289 live cases, 100% with address,
   status, hearing date and Accela link, all point geometry. `stage_hint =
   pre_permit`; bid window opens at the tentative hearing. Filter
   `RECORDALIAS` to the types that precede a buildout (Rezoning, Special Use,
   AB Special Use, Design Exception, General Land Use).
2. `abt.py` — `AlcoholBeverage` (§3 #3). The contacts source. Emit
   `contacts[]` from `BUS_PHONE` / `BUS_OWN_PHONE` / `BUS_OWN_EMAIL`, entity
   from `BUS_NAME` / `BUS_OWNER_NAME`, `sqft` from `AB_SLS_AREA_TTL_SF`.
   Do **not** populate `seats` — the field is filled on 23 of 4,096 rows.
   Clamp dates: the layer contains a `2997` and a `0201`.
3. `cra_grants.py` — `CRACommercialInitiative` (§3 #5). 38 rows, but the only
   source with a real `value_est` (`AWARDEDAMOUNT`, `TOTALPROJECTCOST`).
4. **Then** the state files, to cover what the city layers miss:
   `dbpr_hr.py` (food-service licences and seat counts), `sunbiz.py` (new LLCs
   at commercial addresses), `ahca.py`. Each collector's README section
   records the column layout it depends on and the date it was checked.
5. Geocoder module with Census first, Smarty fallback, on-disk cache committed
   to the data branch. **Not needed for 1–3** — those serve point geometry.
6. `hcaa_ppo.py` monthly PDF parse (§3 #6d) → `relationship` signals.

**Done when:** each collector is green in Actions on a dated run; at least one
entitlement-sourced and one ABT-sourced signal in a tracked submarket appear
in `signals.jsonl`, the ABT one with a phone or email taken from the public
record.

**What actually happened.** All three city collectors are green. Over a
365-day window: 642 records, 223 inside a tracked submarket, **84 qualified** —
40 permits, 26 entitlements, 15 alcoholic-beverage, 3 CRA grants. Seven carry
a phone and an email from the public record, all restaurants in Ybor, Water
Street and the Riverwalk. Steps 4 (the DBPR/Sunbiz/AHCA state files), 5 (the
geocoder — not needed, all four city layers serve point geometry) and 6 (the
HCAA monthly PDF) are NOT done and remain the next work.

Four defects that only reading the real output would have found, each now
tested:

1. **Residential entitlements flooded the list.** 25 of the first 34 qualified
   rows were entitlements at an identical 58, and most were a setback variance
   on a Davis Islands house. Of 160 live cases, 62 were Variance Review Board
   or Design Exception. Only Rezoning, General Land Use, Special Use and AB
   Special Use are fitout-capable now, and `is_fitout` is a hard blocker
   everywhere rather than a display flag.
2. **Every CRA grant was dropped.** Centro Asturiano's $987,850 Special
   Projects grant is Awarded with no completion date and was failing on
   `trade_other`. Awarded grants are precursors now.
3. **A status change is not an opening.** Including `HISTORY_ACT_DT` put Mise
   en Place (licensed 1991), Grand Central Cafe and Mitas Cocina Moderna at the
   top of the call list. Only `CREATEDATE` (a new record) and `PLACARD_DT` (a
   posted notice) make a signal; a status change goes to the directory. Mise en
   Place survives the filter on its own merits — it filed a *new* record in Nov
   2025 at a new address.
4. **An administrative note is not a tenant.** `BUS_NAME` held "No Signoff -
   Initial Approval 4-28-2026", so the list carried a restaurant called No
   Signoff.

Also: the permit layer returns one feature per address unit, so one record
could arrive twice (BLD-26-0522346 as both `5041 W Cypress St` and
`5041 W Cypress St #FS`); ids are deduped at collection.

### Phase 3 — Into the tracker, live — ✅ DONE 2026-09-14 (one gap, below)

1. Routine `trig_01T15GEET3skCnyJVEn92noq`, "Bid Radar — sync signals into the
   tracker": fresh session, `0 13 * * 1-5` (9am ET weekdays, after the 7am
   collector). The prompt is standalone and carries the dedupe rule, the
   human-owned-field rule, the submarket-id→label map, the 180-day prune and
   the digest format.
   **Gap:** the Routine stores no MCP connectors — `create_trigger` refused the
   `connectors` parameter for this organization — so a fired session may not
   have `mcp__github__*`. Step 1 therefore reads the data branch with plain
   `git fetch` / `git show`, which works on the session's own repository
   credentials, and falls back to the GitHub tool only if it is loaded. Watch
   the first firing; if it cannot read the branch either way, the user can
   recreate the Routine from the claude.ai routines UI, where connectors can
   be attached.
2. Page changes to `tampa-bid-radar.html`, published as artifact **version 2**
   at the same URL, capabilities `db` + `downloads` + `mcp{Ideal:[query]}`:
   - **New-signals tray** above the board, reading `signals/` where
     `!dismissed && !promotedTo`, sorted by score, filterable by "with a
     contact" and "score 70+". Cards carry submarket, trade, entity, address,
     size, filed date, bid window, score, the public-record link, and
     click-to-call / click-to-mail contacts. **Promote** writes ONE opportunity
     at `opportunities/sig-{signalId}` — a deterministic id, so promoting twice
     updates one row rather than making two — and records `promotedTo` on the
     signal. **Dismiss** writes only `dismissed`.
   - Opportunity cards gained address, source link, contacts and score.
   - **Send to JobTread** calls the viewer's own `Ideal` connector. The account
     search is the shape observed in §6 Phase 1; `createAccount` is behind a
     confirm with `suffixIfNecessary: true`. Errors branch by code.
   - Rays row updated: AECOM Hunt / Turner as CM, Hillsborough approval
     2026-08-28, both languages.
3. Republished at the same URL, favicon and icon unchanged.

**Done when:** a signal collected by the Action appears in the tray within one
business day with no human step; Promote/Dismiss round-trip survives a reload
for a second viewer; one opportunity pushed to JobTread from the page and found
via `mcp__Ideal__query`.

**What actually happened.** The tray, Promote and Dismiss are covered by 14
browser tests that run the real file in Chromium against a stubbed database and
assert that promote and dismiss touch only the three human-owned fields. The
first Routine firing was 2026-09-14 13:06:31Z and it **worked** — the "within
one business day with no human step" criterion is now OBSERVED, not assumed.
Nobody touched it. The tracker database went from 84 signals to 88 and rising
while the run was still in flight, and the rows it wrote include 14 `dbpr-*`
and 20 `hcaa-*` documents at **version 1** — the two collectors built that
morning, picked up with no change to the Routine's prompt. Existing `abt-*`,
`entitlement-*` and `permit-*` documents incremented to version 2 and 3 rather
than duplicating, which is the idempotent upsert doing its job. A spot check of
a new row: ZIKI'S GREEK STREET FOOD, 615 S Channelside Dr Ste 6, `waterst`,
score 83, one phone from the public record, `dismissed` and `promotedTo` both
untouched. The
JobTread push is now **verified end to end against the live org** (2026-09-14,
with the owner's go-ahead), every call in the exact shape the page sends:

| Call | Observed |
|---|---|
| `jtFindAccount` | `payload.organization.accounts.nodes[0]` → `{id, name}` |
| `jtJobsForAccount` | real jobs with `location.account.id`, `documents.priceSum`, and `customFieldValues.nodes[].value` in `Closed Won` / `Closed Lost` — the values `JT_STAGE` maps |
| `jtCreateAccount` | `payload.createAccount.createdAccount` → `{id, name}`; `suffixIfNecessary: true` is accepted and returns `"… (2)"` on a name collision rather than erroring, which is what the button depends on |
| `deleteAccount` | takes `$.id`; used to undo both test accounts |

Two accounts were created and deleted in the round trip; a `%ZZ TEST%` query
afterwards returns zero rows. Nothing was left in the production org.

### Phase 4 — Close the loop — ✅ DONE 2026-09-14, by a different route

1. ~~`noc.py` — Playwright against the Clerk's ORI search~~ → **replaced.** The
   Clerk's public-records hosts refuse cloud traffic (§3 #6c). The contractor
   of record comes from the permit's own Accela page instead (§3 #10), which
   also carries the job valuation, the real square footage, the applicant's
   phone and email, the owner and the sub list.
   Output is `data/market_share.csv` — contractor × submarket × permits ×
   average job value — plus a section in `summary.md`. The share of that table
   which is ours is our measured share, per submarket.
2. Calibration seed — **done, and it says the opposite of what PLAN assumed.**
   `collect.calibration_seed()` writes `data/calibration_seed.json` and the
   page reads `meta/calibration_seed`.

   PLAN expected the measurement to pull the `avgTI` dial toward the truth.
   The first real measurement (2026-09-14, 29 qualified permits with a value)
   says the dial cannot take it:

   | | |
   |---|---|
   | min | $5,000 |
   | p25 | $400,000 |
   | **median** | **$1,700,000** |
   | p75 | $2,775,433 |
   | mean | $2,653,243 |
   | max | $18,800,000 (Hotel Tampa Riverwalk) |

   The `avgTI` dial spans $50k–$900k. Only the bottom quarter of what qualifies
   is the size of work it models; the rest is hotel renovations and full-floor
   office jobs. Adopting either the mean or the median would pin the slider to
   its maximum and present a clamped number as a calibrated one — worse than
   the $325,000 guess it replaced.

   So the page **shows the quartile spread and offers no adoption** while the
   median sits outside the dial's range, with a line saying which of the two
   readings it implies: the dial is set too small, or the qualifying filter is
   letting in work Ideal does not bid. That is a judgement for a person, and it
   is the most useful thing this measurement produced.

   **It will never touch `winRate`, and no later change should.** Win rate is a
   fact about us; the only honest source is Won/Lost rows a person logged.
   Market share is a different quantity, and a declared job value is not a
   contract value — it is what the applicant told the city the work is worth.
   `tests/test_page.py` asserts the clamp does not happen and that no market
   figure reaches `winRate`.

3. Outcome writeback — **done, in the page rather than the Routine.** PLAN put
   it in the Routine; the Routine stores no MCP connectors (§ Phase 3), so it
   cannot call JobTread at all. A **Refresh** button on a row already linked to
   JobTread reads the job's `Status` custom field and moves the row's stage.
   The mapping is this organization's own eleven values, read from custom field
   `22P6bRnsNu2Y` (type `option`, targetType `job`) on 2026-09-14:

   | JobTread status | Board stage |
   |---|---|
   | New Lead | signal |
   | Estimate with Cost $ · Estimating HOMEE | bidding |
   | Approved · Subcontractor Agreement · Permitting · Construction · Closed Waiting for payments · Paid Waiting to split · Closed Won | won |
   | Closed Lost | lost |

   It deliberately does **not** write `valueActual`. `documents.priceSum` totals
   estimates, change orders and invoices together, and calibration is only
   worth having if the contract value on a Won row is the real one somebody
   typed. The document total is shown as a prompt, not written as a fact.

**Done when:** the tracker's "Modelled vs actual" shows a NOC-derived win rate
per submarket, and a Won job in JobTread flips the row without a human.

**What actually happened.** The win-rate *measurement* exists and is richer
than a NOC would have been — it carries a licence number and a job value per
contractor. It is not yet wired into the calibration panel (step 2). The
JobTread writeback works from the page but is one click, not automatic, because
the Routine cannot hold a connector.

### Phase 5 — Developer / GC direct track — ✅ DONE 2026-09-14
1. `bid_radar/relationships.yaml` — the eight §4 targets with why, action, URL
   and a dated next action, ordered by leverage. `seed_relationships.py` turns
   it into `opportunities/` documents (dry run by default); all eight are
   seeded and on the board as `trade: relationship`.
2. `bid_radar/REGISTRATIONS.md` — the five that are a form somebody has to
   fill in (COMPASS, AECOM Hunt / Turner, TGH vendor, HCAA OpenGov +
   DemandStar, BuildingConnected / PlanHub), each with the URL, the documents
   to have ready, and the specific thing to ask for. The three that are a
   conversation rather than a form are listed separately.
3. The page gained a `relationship` trade so these rows read correctly: no
   dollar figure, no JobTread button, a dashed left border, the *why* shown in
   place of a value, and — verified by test — they never count toward biddable
   or live pipeline.

**Done when:** every §4 row is on the board with a dated next action.

**What actually happened.** All eight are on the board. `owner` is blank on
every one, deliberately: who chases what is not a decision a script should
make. The earliest due date is 2026-09-19 (email Nick Diaz at HCAA about the
next prequalification cycle, since the 2026-09-03 RFP was missed); the
highest-leverage is COMPASS, due 2026-09-26, which opens Moss — the GC for both
Water Street and Gasworx — and 60-odd other Florida GCs in one registration.

---

## 8. What is NOT done

Stated plainly so nobody assumes otherwise. Rewritten 2026-09-14 after the
state sources landed — five of the seven entries that used to be here are now
built, and what remains is here with the reason.

- **AHCA health-care licensure.** The one source with no route found.
  Per-county extracts exist only for Miami-Dade; the Hillsborough path 404s.
  The facility search returns **400** to its own control names because it is a
  client-rendered app with no hidden form fields. The remaining option is
  Playwright against the UI, which works but breaks on their next redesign.
  Left unbuilt deliberately rather than shipped fragile. §3 #6b.
  **Consequence:** the medical-TI signal comes from permits and entitlements
  only, which is later warning than an AHCA licence application would give.
- **Sunbiz is built but produces nothing** until somebody registers for an
  account at `sftp.floridados.gov` and the `SUNBIZ_USER` / `SUNBIZ_PASS`
  secrets exist. Its fixed-width layout is transcribed from the published
  definition, not observed, so `LAYOUT_VERIFIED` is `False` and the first real
  run must confirm the offsets before the output is trusted. §3 #6a.
- **A measured win rate.** The calibration seed is written, but it adopts
  nothing. The `winRate` dial is still a 12% assumption and stays one until
  somebody logs Won and Lost rows on the board — no public source can supply
  it, and market share is not a substitute.
- **A decision on the size mismatch.** The measurement says the qualified
  permits are far larger than the fitouts the model is built around (median
  $1.7M against a $900k dial ceiling). Either the dial is too small or the
  filter is too broad. The page states the choice; nobody has made it.
- **Automatic JobTread writeback.** The push works from the page on a click,
  and every call it makes is now verified against the live org (Phase 3). What
  is missing is the unattended half: `create_trigger` refuses the `connectors`
  parameter for this organization — confirmed twice — so a scheduled session
  gets no connector tools. The remedy the tool itself names is to create the
  Routine from the claude.ai Routines UI. A stage-refresh Routine
  (`trig_01RfGPi58WahpfQWF7iTdk6w`, weekdays 14:00Z) exists and is written to
  check for the connector first and report that it cannot run, rather than
  failing silently.
- **Addresses the Census cannot resolve.** `geocode.py` places most rows, but
  new construction is exactly where it fails — 1050 Water St returns "Tie"
  because TIGER has not caught up, and Water Street is a submarket we care
  about. Those rows keep `needs_geocode: True` and never qualify. A paid
  fallback (Smarty) would close it; nothing else will.
