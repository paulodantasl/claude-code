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

Every JobTread call the page makes has been run against the live org and seen
to work — none of it is assumed. On 2026-09-14 the account lookup, the job and
status read, `createAccount` (including `suffixIfNecessary`, which returns
`"… (2)"` on a name collision instead of failing) and `deleteAccount` were all
exercised in the shapes the page sends. The two accounts created to prove the
write path were deleted immediately and nothing was left in the org. Shapes are
recorded in PLAN.md §6 Phase 1 and Phase 3.

Nothing in the tracker page calls a shape that has not been observed.

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

---

## The developer and GC track (Phase 5)

Eight relationship rows now sit on the board next to real jobs, as
`trade: relationship` — no dollar figure, no JobTread button, a dashed border,
and the *why* shown where a value would be. They never count toward biddable or
live pipeline; a test enforces that.

`relationships.yaml` is the source of truth and `seed_relationships.py` turns it
into board rows (dry run by default). **`REGISTRATIONS.md` is the one to read** —
five of the eight are a form somebody has to fill in, with the URL, the
documents to have ready, and the specific thing to ask for.

Ordered by leverage:

1. **COMPASS** — one registration opens Moss (GC for both Water Street and
   Gasworx) and 60-odd other Florida GCs. Due 2026-09-26.
2. **AECOM Hunt / Turner** — named CM for the Rays district, approved
   2026-08-28. The bowl is out of reach; the fitouts around it are not.
3. **Sunwest Construction** — the most reachable ownership on the board.
4. **JPRE + Archer** — Gasworx retail leasing. They know the tenant a year
   before any public record does.
5. **TGH vendor application** — ask for the construction-services category;
   the default routing is clinical supply.
6. **HCAA** — the prequal RFP closed 2026-09-03 and we missed it. Email Nick
   Diaz about the next cycle. Due 2026-09-19, the earliest date on the list.
7. **BuildingConnected / PlanHub** — an incomplete profile is invisible.
8. **SPP** — a two-year play, not a bid.

`owner` is blank on every row on purpose. Who chases what is not a decision a
script should make.

---

## Who is building fitouts here (Phase 4)

The plan's route to a measured win rate was the Hillsborough Clerk's Notices of
Commencement. **Both of the Clerk's public-records hosts refuse traffic from a
cloud runner** — `ConnectTimeout` on `pubrec6.hillsclerk.com`,
`ConnectionError` on `pubrec.hillsclerk.com`, while `www.hillsclerk.com`
answers 200 from the same machine. That route is closed.

The replacement is better than the original, and it was sitting in the data the
whole time. Every permit row already carries a per-record Accela URL, and that
page holds every field the ArcGIS layer omits:

| On the page | What it gives us |
|---|---|
| **Licensed Professional** | The **GC of record** — company, Florida licence number, email |
| **Applicant** | Name, work phone, email |
| **Owner** | Name and mailing address |
| **Tenant contact** | Where the record has one |
| **Job Value** | The valuation the ArcGIS layer does not carry |
| **Sq Ft** | The real floor area |
| Additional Licensed Professionals | Each sub's company and licence |

Verified on `BLD-26-0526061` — the Wagamama fitout at 1050 Water St: GC *TWT
Restaurant Design Construction & Development Company*, licence CBC1262713, with
an email; applicant Stephen Torres with a phone and an email; owner *Wst 1010
Water Street Llc c/o Strategic Property Partners Llc*; Job Value $300,000;
4,525 sq ft; Duffy Electric and Johnson Controls on the sub list.

So this closes the biggest gap in the system, not just the win-rate question. A
permit row stops being *something happened at this address* and becomes a lead
with a name, a number and a real dollar value.

`accela.py` parses the page by its printed labels rather than its DOM — the DOM
is generated and brittle, the labels are not. `enrich.py` caches parsed results
by record id on the data branch, so a second run fetches only what is new.
Enrichment happens **before** scoring, because value and contacts both move the
score.

Accela's speed is not dependable — the same 223 pages took ten minutes one run
and were still going at forty-four the next — so enrichment is bounded twice
over: at most `ACCELA_MAX_FETCH` pages and at most `ACCELA_BUDGET_S` seconds of
fetching, with the cache flushed every 20 pages. A slow day leaves part of the
back-catalogue for tomorrow; it never leaves the job hanging.

**`market_share.csv`** is the output: contractor of record × submarket ×
permits × average job value. The share of that table which is ours is our
measured share, per submarket — which is what two of the five calibration dials
have been guessing at.

The first live run put four bad rows in that table, and all four are fixed:
a street address read as a company name (the record prints name, then address,
then licence, and the address looked like a firm), a qualifier and their firm
run together on one line, and two job values — $280,000,000 and $500 — that are
data entry on the record rather than real. A suspect value stays on the row,
flagged, but is left out of the averages. These mattered because every one of
them would have gone straight onto a cold call.

### The calibration seed, and what it actually found

The `avgTI` dial — average contract — has been guessing at $325,000. The
collector now measures it: the declared job value of every qualified fitout
permit in our submarkets, suspect values excluded, written to
`calibration_seed.json` and seeded into the tracker.

The first measurement, 29 permits over twelve months:

| | |
|---|---|
| p25 | $400,000 |
| **median** | **$1,700,000** |
| p75 | $2,775,433 |
| largest | $18,800,000 — Hotel Tampa Riverwalk |

**The dial only goes to $900,000.** Only the bottom quarter of what currently
qualifies is the size of work the model is built around; above that sit hotel
renovations and full-floor office jobs. So the page shows the spread and
offers no one-click adoption while the median is out of range — pinning the
slider to its maximum would look like calibration and be a worse number than
the guess it replaced.

That leaves a real question on the screen for someone to answer: is the dial
set too small, or is the qualifying filter letting in work we do not bid?
Either way it is worth knowing, and it is the most useful thing this
measurement produced.

**Win rate stays where it is.** It is a fact about Ideal, and the only place it
can honestly come from is a Won or Lost row someone logged on the board. Market
share is a different number, and a declared job value is not a contract value —
it is what the applicant told the city the work is worth.

## JobTread status writeback

A **Refresh** button on any row already linked to JobTread reads the job's
`Status` custom field and moves the row's stage. The mapping is this
organization's own eleven values, read from custom field `22P6bRnsNu2Y`:

| JobTread status | Board stage |
|---|---|
| New Lead | signal |
| Estimate with Cost $ · Estimating HOMEE | bidding |
| Approved · Subcontractor Agreement · Permitting · Construction · Closed Waiting for payments · Paid Waiting to split · Closed Won | won |
| Closed Lost | lost |

It deliberately does **not** write the contract value. `documents.priceSum`
totals estimates, change orders and invoices together, and calibration is only
worth having if the value on a Won row is the real contract somebody typed. The
document total is shown as a prompt, not written as a fact.

This lives in the page rather than the daily Routine because the Routine stores
no MCP connectors and cannot call JobTread at all.
