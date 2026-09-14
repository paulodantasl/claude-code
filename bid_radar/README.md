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
