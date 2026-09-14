# Tampa Bid Radar

Market intelligence for Ideal Construction, aimed at one question a general
contractor actually has: **which tenant fitouts are coming out to bid, where,
and when.**

`tampa-bid-radar.html` is a single standalone file — open it in a browser, no
build step. It is also published as an Artifact, where it gains a shared
team database (see *Persistence* below).

---

## What changed from v1

v1 was a **market-sizing model**. It took a public development pipeline, applied
four assumptions, and told us where to concentrate: Ybor, Water Street,
Westshore, Davis Islands. That question is now answered, and re-running the
dials next month will not produce a new answer.

v2 turns it into a **tracker** by adding the two layers a sizing model cannot have:

| Layer | What it is | Why it matters |
|---|---|---|
| **1 — Pipeline** | One row per real fitout: tenant, submarket, stage, est. value, bid date, owner, next action | The model forecasts *fitouts*; only this names *jobs* |
| **2 — Calibration** | Won/Lost rows carry the actual contract value; the tool back-solves win rate and average contract | Makes the model falsifiable — the dials stop being guesses |
| **3 — Signals** | The public data trail each fitout leaves, ranked by warning time | Tells us where layer 1 gets filled from |

The submarket table gained a **Live** column: modelled *Our share* against what
is actually in the pipeline. The gap is the work nobody is chasing yet.

### Bugs fixed from v1

- **Unit/fitout mismatch.** `agg()` added `p.units` for every project but only
  added fitouts for projects whose bid window fell inside the chart horizon.
  Ybor Harbor (2,586 units, delivers 2034) contributed its units and zero
  fitouts, so Ybor City read as 7,586 units producing Gasworx's fitouts alone.
  In-horizon and beyond-horizon units are now separated and both are shown.
- **Sortable headers did nothing.** `sortKey`/`sortDir` existed and the CSS said
  `cursor:pointer`, but no click handler was ever bound.
- **Persistence never worked.** `save()`/`load()` were guarded on
  `window.storage`, which does not exist in a browser, so the dials silently
  reset on every reload.
- **Hardcoded dates.** The "today" marker was `2026.7` and the year axis was a
  literal `[2026…2031]`; both now derive from the clock.
- **Untranslated strings.** `units`, `fl`, `delivery`, `fitouts` stayed English
  in PT-BR mode.
- **Chart geometry.** Segments were sized against a hardcoded `180px` inside a
  `230px` box (`180px` on mobile), so bars never filled and could overflow.
  Heights are now percentages of the flex-sized stack.
- Dead code in `renderChart` (`h`, and a ternary returning `1` either way);
  `money()` rendering `$0k`; no HTML escaping (harmless with static data,
  not once permit strings flow in); no dark theme.

### Model changes, stated rather than buried

- **Absorption is now a dial** (default 2 years, the v1 constant). A 5,000-unit
  master plan does not absorb tenants on a hotel's curve; making it adjustable
  is the honest interim step before per-project absorption.
- Known limits are printed on the page, not just here: horizon truncation,
  the Gasworx/Ybor Harbor double-count, one absorption number for all project
  types, and access being a judgement rather than a measurement.

---

## Finding the tenants

Every fitout leaves a public trail before it goes out to bid. Ordered by how
much warning it gives:

| Warning | Signal | Source | In our stack |
|--:|---|---|---|
| 12–24 mo | Retail leasing brochure / anchor announcement | Developer leasing page; CoStar, Crexi, LoopNet | — |
| 9–18 mo | Rezoning / site plan (DRC) submittal | Tampa Construction Services; Hillsborough DSD agendas | — |
| 6–12 mo | New LLC at a submarket address | [Sunbiz daily data downloads](https://dos.fl.gov/sunbiz/other-services/data-downloads/daily-data/) — fixed-width, free, weekdays | partial |
| 6–12 mo | AHCA facility licence application | AHCA facility locator / licensure filings | — |
| 4–9 mo | Alcoholic beverage licence (2COP/4COP) | [DBPR ABT daily licence status data](https://www2.myfloridalicense.com/alcoholic-beverages-and-tobacco/daily-license-status-reporting-data/) | — |
| 3–9 mo | DBPR food service / lodging licence | [DBPR public records extracts](https://www2.myfloridalicense.com/instant-public-records/) (free CSV) | — |
| 3–6 mo | Local business tax receipt | Tampa / Hillsborough BTR | — |
| 0–4 mo | **Building permit application** | `arcgis.tampagov.net/.../PermitsAll/FeatureServer/0` — public, no auth | **live** |
| 0 | Notice of Commencement | [Hillsborough Clerk ORI](https://pubrec6.hillsclerk.com/ORIPublicAccess/) (search UI, no API) | — |

**The point: we already own the hard half.** `permit_scraper` covers City of
Tampa (public ArcGIS feed) and Hillsborough (Accela), with fuzzy company
matching, SQLite storage and Slack alerts. `ideal_apis` has the dedupe ledger,
approval gates and JobTread push. Neither is connected to this tracker.

The work is not building a scraper. It is:

1. Filtering existing permit output to these submarkets and to fitout permit
   types, rather than the national-retailer watch list in `companies.yaml`.
2. Adding the **licence feeds** above the permit line — ABT and AHCA are the two
   leading indicators for the exact verticals we already win (F&B and medical).
3. Writing matches into the pipeline instead of a CSV.
4. Scraping recorded **Notices of Commencement** to measure our *real* win rate
   and *real* average contract per submarket — which replaces two of the five
   dials with facts.

> Note: the Tampa ArcGIS endpoint is documented in
> `permit_scraper/targets/counties.yaml`. It could not be reached from the
> sandbox this file was written in (egress policy), so treat it as unverified
> until someone runs `python -m permit_scraper run --county city_tampa`.

---

## Suggested build order

> Superseded in detail by **[PLAN.md](PLAN.md)** — the execution plan for the live lead engine, with verified sources, definitions, architecture and per-phase acceptance criteria.


1. **Feed → pipeline.** A writer that turns a classified permit or licence row
   into a pipeline row. Highest value, smallest change: it is the only step that
   makes the tracker self-filling.
2. **NOC backfill.** Historical Notices of Commencement give us a measured win
   rate per submarket immediately, without waiting to log new bids.
3. **ABT + AHCA collectors.** Two new adapters alongside the existing scrapers.
4. **Per-project absorption**, replacing the single dial.
5. **Insurance/restoration tracker.** Called out on the page as a blind spot —
   different drivers (storm landfall, building-stock age, carrier panels),
   so it needs its own inputs, not a tab on this one.

---

## Persistence

| Where | Storage |
|---|---|
| Published Artifact | Shared `db` — every teammate sees the same pipeline; dials live in `meta/dials`, rows in `opportunities/` |
| Standalone file | `localStorage`, per browser |

The page detects which it has and says so in the header strip. It renders
four **illustrative placeholders** when the pipeline is empty so the board is
not a blank shell; they are labelled `example`, never counted in calibration,
and disappear on the first real row.

---

## The permit feed (Phase 0, live)

The tracker's Signals layer is no longer a list of sources we *could* use —
the first one runs.

| File | What it is |
|---|---|
| `submarkets.geojson` | The eight tracked submarkets as polygons. Generated by `build_submarkets.py`; do not hand-edit. |
| `build_submarkets.py` | Core rings drawn on street and water boundaries, plus the trade-area buffer. Build-time only (needs `shapely`). |
| `geo.py` | Point → submarket, by precedence. No third-party dependency. |
| `classify.py` | Trade, stage and tenant name from a permit record. |
| `collect.py` | Fetch → filter → classify → `data/signals.jsonl` + `data/summary.md`. |
| `discover_*.py` | The three discovery passes that established what the sources actually contain. Output on the `bid-radar-data` branch. |
| `tests/` | 113 tests, every fixture taken verbatim from the live layer. |

### Where the output goes

GitHub Actions (`.github/workflows/bid-radar-collect.yml`) runs the collector
at 7am ET on weekdays and commits `bid_radar/data/` to the **`bid-radar-data`
branch**. That branch is the hand-off: a Claude session can read GitHub but
cannot reach any permit host, so it picks the data up from there and writes it
into the tracker's database (Phase 3).

### What the permit source can and cannot tell us

This matters more than the code. Established by querying the layer, not
assumed:

- **It publishes at issuance.** `PROJECTSTATUS` is only ever `Issued` or
  `Revision`. There is no application or in-review state, so the layer cannot
  be asked "what is coming out to bid". Intake to issue ran 15–66 days (median
  35).
- **`EARLY START` is the exception and the whole point.** The city releases
  interior non-structural work while the main permit is still pending. Those
  rows have a live buyout window; the summary lists them first. Three of the
  first sixteen in-submarket records were EARLY START.
- **There is no valuation, applicant, owner or contractor field.** Those
  columns are absent from the output rather than guessed. The tenant is parsed
  out of the project name and description and left blank when it cannot be read
  with confidence.
- **`OCCUPANCYCATEGORY` is the useful field** — the Florida Building Code
  occupancy the applicant filed under. `A-2` is a restaurant, `B-5` an
  outpatient clinic, `M-4` retail. That classifies trade far more reliably
  than reading the description, and a test asserts every code in the live
  vocabulary is mapped.
- **Volume is low.** 29 commercial records citywide in 90 days, 16 in a
  tracked submarket. The window is 365 days for that reason, with the last 90
  called out separately.

### The three layers we did not know existed

Discovery turned up three more layers on the same host, all public and all
point geometry (see PLAN.md §3):

- **`ActiveEntitlementLocations`** — 289 rezoning, variance and special-use
  cases, every one still pending, each with an address, a status and a
  tentative hearing date. This is the 9–18-month signal the plan had no source
  for.
- **`AlcoholBeverage`** — 4,096 records carrying business name, owner name,
  phone and email. It is the only source in the system with a contact channel,
  and it makes Tampa's own data a better route than the DBPR state files.
- **`CRACommercialInitiative`** — 38 CRA grants for commercial interior and
  façade work, with a named applicant and an award amount: the only source
  that yields a real dollar value.

Those are Phase 2.

---

## Scoring (Phase 1)

`score.py` turns a signal into a 0–100 score and a qualify/no decision, per
PLAN.md §2.3 and §2.4. `blocklist.yaml` holds the names we will never win —
national programmes with in-house construction, and public bodies whose work
comes through a procurement portal rather than a tenant introduction.

Two honest adaptations, because the permit source cannot supply what the plan
assumed:

- **Value is unknown on every permit row.** The plan already scores an unknown
  value at 8/20, so permits take that. The CRA grant layer (Phase 2) is the one
  source with a real dollar figure.
- **Nothing has a contact channel.** The qualified-lead definition requires
  one; enforcing it as a hard gate would qualify zero rows. It is a *soft*
  blocker instead — the row still qualifies, carries `needs_contact`, and joins
  the queue that Phase 2 enriches from the alcoholic-beverage layer.

Hard blockers, which do disqualify: outside every submarket, trade `other`
(except a strip-out, where the trade is genuinely not declared yet),
blocklisted, already awarded, or below the size gate.

### Two rules that came out of labelling the first real run

- A **demolition** record returns `other` and never consults keywords.
  Otherwise "demolition of two story wood framed office buildings" reads as an
  office lead and a teardown lands on the call list.
- A **strip-out** — the record says the space is being emptied and the
  build-back comes under a separate permit — gets its own stage. The tenant is
  committed, the fitout has not been bid, and the trade is declared later.
  Detection only fires when the record itself says the build-back is separate;
  a false positive would demote a real fitout to `other` and lose the lead.

### The funnel, measured

29 commercial permits in 90 days → 16 in a tracked submarket → **4 qualified**:
Wagamama Pan Asian (73), Edikted (63), Altieri Ins. Consultants (58),
Nationwide (58). Nineteen of the 29 were already-issued permits, which the
definition correctly refuses to call outreach.

**Four qualified leads a quarter, none with a phone number, is the honest
ceiling of the permit source on its own.** Phase 2 is where the volume is.

## Into JobTread (Phase 1)

`to_leads.py` maps qualified signals onto the existing `ideal_apis` pipeline —
`LeadRecord` → `ApprovalBatch` → the approve → JobTread → QUO flow, unchanged.
Dry run by default:

```
python bid_radar/to_leads.py --signals bid_radar/data/signals.jsonl
python bid_radar/to_leads.py --signals bid_radar/data/signals.jsonl --write
```

Signals with a contact become **contact leads** and are eligible for a JobTread
push. Signals without become **intel leads** — the slot the batch already has
for non-contactable rows. Every permit signal is intel today.

The JobTread handshake was observed live through the `Ideal` connector, not
assumed: org `22P6bRn5p6Pn`, 259 customer accounts, and the `accounts … name
like` and `createAccount` shapes are recorded in PLAN.md §6 Phase 1. Nothing in
the tracker page will call a shape that has not been observed.

---

## The other three sources (Phase 2)

Discovery turned up three more Tampa layers on the same host as the permits —
all public, all point geometry, no geocoder needed.

| Module | Layer | What it adds |
|---|---|---|
| `sources/entitlements.py` | `ActiveEntitlementLocations` | Live rezoning, land-use and special-use cases with a published hearing date. The earliest signal in the system. |
| `sources/abt.py` | `AlcoholBeverage` | **The only source with a phone number or an email.** |
| `sources/cra_grants.py` | `CRACommercialInitiative` | **The only source with a real dollar figure.** |

`arcgis.py` is the one place that talks HTTP; `collect.py` orchestrates, and a
source that fails costs its own section of the report, not the report.

### Over a 365-day window

642 records → 223 inside a tracked submarket → **84 qualified**. Seven carry a
phone and an email from the public record — all restaurants in Ybor, Water
Street and the Riverwalk.

### What each source will and will not tell you

- **Entitlements** name no applicant. The address is the lead and the trade is
  undeclared, except on alcoholic-beverage special-use cases. Only Rezoning,
  General Land Use, Special Use and AB Special Use count: of 160 live cases, 62
  were Variance Review Board or Design Exception, and nearly all of those are a
  setback on somebody's house.
- **Alcoholic-beverage records** move on three dates and only two mean work: a
  new record (`CREATEDATE`) and a posted placard (`PLACARD_DT`). A status change
  alone is administrative — including it put Mise en Place, licensed since 1991,
  at the top of the call list. Seat counts are filled on 23 of 4,096 rows and
  are not used. `abt_directory.csv` holds every Active venue in the eight
  submarkets with contact details: a prospecting list, not leads.
- **CRA grants** are a lead when Awarded with no completion date — committed
  money, outstanding work. `TOTALPROJECTCOST` is the job; the grant is a slice.

## The tracker page (Phase 3)

The published artifact gains a **New signals** tray above the board, fed from
the machine-owned `signals/` collection. Promote creates one opportunity at a
deterministic id and stamps `promotedTo` on the signal; Dismiss stamps
`dismissed`. Those three fields plus `notes` are the only things a person owns,
and the daily sync never writes them — which is why a collection run cannot
undo a decision somebody made.

`Send to JobTread` on an opportunity calls the viewer's own `Ideal` connector
with their credentials, searching for an existing customer account before
offering to create one.

**The daily loop:**

```
07:00 ET  GitHub Action collects → commits bid_radar/data/ to bid-radar-data
09:00 ET  Claude Routine reads that branch → writes signals/ → digests
   →      the tray is populated when somebody opens the page
```

The Action needs no credentials; the Routine needs no network beyond GitHub.
Neither can reach a Tampa data source, and neither needs to.

### Running the browser tests

```
pip install playwright && python -m playwright install chromium
pytest bid_radar/tests
```

They load the real HTML file, stub `claude.use`, and assert the page renders
with no capabilities at all — a broken tray is worse than a broken collector,
because nobody sees a stack trace.
