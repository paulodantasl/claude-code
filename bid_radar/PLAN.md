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
| Tampa permits scraper — public ArcGIS FeatureServer, no auth | `permit_scraper/scrapers/arcgis_api.py`, target `city_tampa` in `targets/counties.yaml` | Written; never observed running — DISCOVER |
| Hillsborough (Accela/HillsGovHub), Pinellas, Pasco scrapers | `permit_scraper/scrapers/accela.py` | Written; `use_ai_agent: true` on Hillsborough |
| `RawPermit` dataclass (has lat/lon, value, sqft, filed/issued, parties) | `permit_scraper/scrapers/base.py` | Reuse as-is |
| SQLite `permits` table, unique on `(source_id, county_id)` | `permit_scraper/storage/models.py` | Reuse |
| Fuzzy **company** matcher (Publix/Amazon watch list) | `permit_scraper/agents/classifier.py` | Wrong tool for fitouts — do not extend; write `FitoutClassifier` |
| Lead model, dedupe ledger, approval batches, JobTread push, QUO queue | `ideal_apis/ideal_apis/pipeline/{models,ledger,approvals,apply,jobtread_export}.py` | Reuse; extend `Source` literal |
| Daily cron pattern (7am ET weekdays, py3.12, upload-artifact) | `.github/workflows/daily-leads.yml` | Clone for `bid-radar-collect.yml` |
| Property appraiser adapters | `permit_scraper/scrapers/property_appraiser.py` | DISCOVER whether Hillsborough (HCPA) is covered |

---

## 2. Definitions the whole system hangs on

### 2.1 Submarkets (8) — `bid_radar/submarkets.geojson`
Polygons plus a 0.5-mile trade-area buffer. Draw from street boundaries;
**acceptance test: geocode all 15 projects in the tracker's `P` array and assert
each falls inside its assigned polygon.** Store the 15 geocoded points as the
fixture `bid_radar/tests/fixtures/projects.geojson`.

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
brand         normalized brand if recognizable, else null
trade         medical | restaurant | retail | office | hospitality | other
stage_hint    pre_permit | applied | issued | commenced
value_est     $ from permit valuation, or null
sqft          from permit, or null
seats         from DBPR H&R licence, or null
filed_at      the source's own date
bid_window    {open, close} inferred per §2.4
contacts[]    {kind: phone|email|agent, value, from}   — only from public records
source_url, retrieved_at
confidence    0–1 from classifier
```

### 2.3 Qualified lead — ALL of:
- (a) `hood` non-null;
- (b) `trade` ≠ other;
- (c) `value_est ≥ 75,000` or `sqft ≥ 1,200` or `seats ≥ 30`, **or** the signal
  is a licence-type source (abt/ahca/dbpr_hr) where value is unknowable;
- (d) bid window opens within 9 months; for `permit`, `stage_hint = applied`
  and `filed_at ≤ 30 days` (an *issued* fitout permit is already awarded —
  keep it, tag `late`, route to §4 win-rate analysis, not outreach);
- (e) an identifiable entity with ≥ 1 public contact channel;
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

## 3. Data sources — verified state and discovery steps

| # | Source | Warning | Access | Status | Executor must DISCOVER |
|---|---|---|---|---|---|
| 1 | **City of Tampa permits** — `arcgis.tampagov.net/arcgis/rest/services/Planning/PermitsAll/FeatureServer/0`, date field `APPLICATIONDATE` | 0–4 mo | public, no auth, JSON | in repo, unobserved | (i) `returnDistinctValues=true` on `PERMITTYPE`, `WORKCLASS`/`SUBTYPE`, `STATUS` → write `bid_radar/data/vocab_tampa.json`; build the fitout filter **from that vocabulary**, not from guesses. (ii) Confirm features carry point geometry. (iii) Confirm which fields hold applicant / contractor / valuation. |
| 2 | **Hillsborough permits** — HillsGovHub Accela `aca-prod.accela.com/HCFL` | 0–4 mo | browser scrape | in repo, `use_ai_agent: true` | Whether the rule-based Accela scraper works without the AI agent; unincorporated county matters least for these 8 submarkets (all inside city limits except parts of Dale Mabry/airport) — **deprioritize** |
| 3 | **DBPR ABT** alcoholic-beverage licences — daily licence status data (free CSV) `www2.myfloridalicense.com/alcoholic-beverages-and-tobacco/daily-license-status-reporting-data/` | 4–9 mo | public file | VERIFIED page exists | Column layout; whether pending/new applications appear or only issued; county field for Hillsborough filter |
| 4 | **DBPR Hotels & Restaurants** food-service and lodging extracts (free CSV) `www2.myfloridalicense.com/instant-public-records/` | 3–9 mo | public file | VERIFIED extracts exist | File names, refresh cadence, seat-count column |
| 5 | **Sunbiz** daily corporate filings (fixed-width, weekdays, SFTP or browser) `dos.fl.gov/sunbiz/other-services/data-downloads/daily-data/` | 6–12 mo | public file | VERIFIED daily files exist | Fixed-width column definitions (`…/corporate-data-file/`); principal-address fields; filter to ZIPs 33602 33605 33606 33607 33609 33611 33616 then geocode + polygon |
| 6 | **AHCA** health-care facility licensure | 6–12 mo | public | not yet researched | Which AHCA data product lists *applications* (not only licensed facilities); if none, use FloridaHealthFinder licensed-facility deltas as a later-stage proxy |
| 7 | **Hillsborough Clerk** official records — Notices of Commencement `pubrec6.hillsclerk.com/ORIPublicAccess/` | 0 (already awarded) | search UI, no API | VERIFIED no API | Playwright search by document type + date range + legal description/address; this is the **win-rate** dataset, not an outreach dataset |
| 8 | **HCAA Planned Procurement Opportunities** — monthly PDF at `tampaairport.com/sites/default/files/<yyyy-mm>/Planned Procurement Opportunities Report - <Month> <yyyy>.pdf`; OpenGov portal `procurement.opengov.com/portal/tampaairport`; DemandStar | varies | public | VERIFIED | Stable URL pattern; parse the table (PDF) monthly |
| 9 | **Geocoding** for sources 3–7 | — | — | needed in Actions | Census Geocoder (free, batch, no key) first; Smarty (keyed, already in `ideal_apis.address`) as fallback |

**Not to build:** Hillsborough BTR (late, low value), CoStar (paid; broker
relationships replace it), Related Group (no public prequal found — tenant-side
only, as the tracker already says).

---

## 4. Direct paths to master developers and their GCs — VERIFIED 2026-09-14

These are relationship rows, not data rows. Seed them into `opportunities/` as
`trade: relationship` with a next action and owner so they get worked.

| Target | Fact | Action |
|---|---|---|
| **Moss** — GC for Water Street (Cora; entertainment venue JV with Barton Malow) *and* Gasworx (office + Olivette) | Prequalifies subs through **COMPASS** (`compass.bespokemetrics.com`), used by 60+ Florida GCs | Register on COMPASS once → opens Moss and every other FL GC on it. Highest-leverage single action on this list. |
| **AECOM Hunt / Turner** — CM for the Rays stadium district, named 2026-07-17 | Deal approved by Hillsborough 2026-08-28; site prep Sept 2026, demolition Dec, foundations Mar 2027, Opening Day 2029; 113-acre mixed-use "Innovation Edge" at the Hillsborough College Dale Mabry site | Get on both firms' sub/prequal lists now; the district's retail/F&B fitouts follow the bowl. **Update the tracker row** (currently names Hines/Populous only). |
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

### Phase 0 — Prove the feed (first PR)
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

**Done when:** the workflow is green on `workflow_dispatch`; `summary.md` on
`bid-radar-data` lists real Tampa fitout permit applications from the last 90
days by submarket, each with permit number, address, applicant and source URL;
all 15 fixture projects pass the polygon test. *This alone is actionable for
the user — flag it to them the moment it lands.*

### Phase 1 — Classify, score, and shake hands with JobTread
1. `bid_radar/classify.py` — `FitoutClassifier` (trade from work class +
   description keywords + applicant name patterns such as "DDS", "DMD",
   "Dental", "MD", "PA", "Grill", "Kitchen", "Salon"; `stage_hint`;
   confidence). Unit-test against 30 rows sampled from Phase 0 output,
   hand-labelled in `bid_radar/tests/fixtures/labels.csv`.
2. `bid_radar/score.py` — §2.3 + §2.4. `blocklist.yaml`.
3. Extend `ideal_apis` `Source` literal with `permit abt dbpr_hr sunbiz ahca noc`;
   `bid_radar/to_leads.py` maps qualified signals → `LeadRecord` → existing
   `ApprovalBatch` (`ideal-api leads collect` path) so the approve → JobTread
   → QUO flow works unchanged, dry-run by default.
4. From the session, confirm the JobTread handshake with one
   `mcp__Ideal__query` call (`currentGrant → organization → id`, then
   `accounts where name like`) — observe the real response shape before any
   page code calls it.

**Done when:** precision ≥ 0.8 on the labelled sample for `trade`; scores are
written into `signals.jsonl`; `ideal-api leads status --show-leads` lists
permit-sourced leads with `source_url`; one dry-run JobTread push validated.

### Phase 2 — Leading indicators (the licence feeds)
1. `abt.py`, `dbpr_hr.py`, `sunbiz.py`, `ahca.py` — each: fetch → `RawSignal`
   → geocode → polygon → classifier. Discovery steps in §3 come first, and
   each collector's README section records the column layout it depends on
   and the date it was checked.
2. Geocoder module with Census first, Smarty fallback, on-disk cache
   committed to the data branch (addresses repeat).
3. `hcaa_ppo.py` monthly PDF parse (source #8) → `hcaa_ppo` signals typed
   `relationship`.

**Done when:** each collector is green in Actions on a dated run; at least one
ABT-sourced and one Sunbiz-sourced signal in a tracked submarket appear in
`signals.jsonl` with contacts populated from the public record.

### Phase 3 — Into the tracker, live
1. Routine per §5 (`create_trigger`, fresh session, 9am ET weekdays) whose
   prompt is complete and standalone: fetch → diff → `write_db` batch → prune
   → digest. Dedupe rule and human-owned-field rule stated in the prompt.
2. Page changes to `tampa-bid-radar.html`:
   - **New-signals tray** above the board: `signals/` where
     `!dismissed && !promotedTo`, sorted by score; each card shows hood,
     trade, entity, address, value/seats, filed date, source link, contacts;
     buttons **Promote** (creates `opportunities/{id}` copying the record,
     sets `signals/{id}.promotedTo`) and **Dismiss**.
   - Extend opportunity cards with address, source link, contacts.
   - **Send to JobTread** on an opportunity, via the `mcp` capability
     (`capabilities: {db:{}, downloads:true, mcp:{servers:[{server:"Ideal",
     tools:["query"]}]}}`) — only after Phase 1 step 4 observed a real
     request/response; store the returned account id on the row.
   - Update the Rays row (`dev` → add AECOM Hunt / Turner as CM; note
     Hillsborough approval 2026-08-28).
3. Republish the artifact at the same URL (keep favicon/icon).

**Done when:** a signal collected by the Action appears in the tray within
one business day with no human step; Promote/Dismiss round-trip survives a
reload for a second viewer; one opportunity pushed to JobTread from the page
and found via `mcp__Ideal__query`.

### Phase 4 — Close the loop
1. `noc.py` — Playwright against the Clerk's ORI search, last 24 months,
   document type Notice of Commencement, filtered to the polygons → per-hood
   table of contractor × count × (stated value where present). Output
   `data/noc_market_share.csv` + a README section: **our measured share per
   submarket** and the real average fitout contract where NOCs state value.
2. Calibration seed: write `meta/calibration_seed` with those actuals so the
   dials start from measurement.
3. Outcome writeback in the Routine: for opportunities with a JobTread account
   id, read job status via `mcp__Ideal__query` and move stage to Won/Lost.

**Done when:** the tracker's "Modelled vs actual" shows a NOC-derived win rate
per submarket, and a Won job in JobTread flips the row without a human.

### Phase 5 — Developer / GC direct track
1. `bid_radar/relationships.yaml` from §4, seeded to `opportunities/` as
   `trade: relationship` rows with owner + next action + date.
2. A short `bid_radar/REGISTRATIONS.md` checklist the user completes by hand
   (COMPASS, BuildingConnected, TGH vendor form, HCAA OpenGov/DemandStar,
   AECOM Hunt / Turner prequal), each with the URL and what to enter under
   *Work Performed* / *Service Area*.

**Done when:** every §4 row is on the board with a dated next action.

---

## 7. Efficiency notes for the executor

- Phase 0 is the only phase with real uncertainty (whether the ArcGIS layer
  behaves as `arcgis_api.py` assumes). Start there; everything else is
  plumbing over verified files.
- Validate in Actions with `days_back=7` while iterating; switch to 90 for the
  first real run.
- Do not refactor `permit_scraper` or `ideal_apis` beyond the `Source` literal
  and a new import; add modules under `bid_radar/` and import across.
- Tests: pytest under `bid_radar/tests/`; run them locally (they use fixtures,
  no network) before every push.
- If a source's layout differs from what §3 expects, **update §3 in the same
  PR** — this file is the system of record for what was observed.
- Report to the user after Phase 0 and Phase 3 land; those are the two moments
  the tool changes what they can do on Monday.
