# API candidates for Ideal Construction

Curated from [public-apis](https://github.com/paulodantasl/public-apis) (1,717 entries, 50 categories),
filtered against what a Florida GC actually does: land/lot screening, permits, takeoff and estimating,
bid packages, public work compliance, field logistics, and lead gen.

Everything below is scored against the modules already wired in `ideal_apis/` so we don't pay twice.

**Build status.** Both fixes in section 2, all of Tier A, and four of Tier B are now implemented and
covered by tests — see the status column in section 3. Two Tier A picks turned out to already have
client methods (`address.extract_addresses`, `government.epa_envirofacts`); they were never exposed
on the CLI, so the work there was wiring, not building. Three Tier B picks were deliberately left
out and section 3.1 says why.

---

## 1. Already covered — do not re-buy

| Need | Wired as | Source APIs |
|---|---|---|
| Address normalization for JobTread | `address` | Smarty US Street / Autocomplete |
| Phone + email hygiene before QUO | `validation` | Numverify, Kickbox, EVA |
| Dental / commercial lead gen | `leads` | NPPES, Yelp, CMS |
| Permit intel | `permits` | Socrata, Data.gov (+ `permit_scraper`) |
| Scheduling + storm/restoration leads | `weather` | NWS, Open-Meteo, NOAA hail, RainViewer, Storm Glass |
| Public bids, sub vetting | `government` | USAspending, Federal Contracts, FastDOL, Census |
| Bid-page / listing metadata | `web` | Microlink |
| Invoices, COIs, proposals | `documents` | DocStruct, OCR.Space, BuildPDF, PandaDoc |
| Drive time, isochrones | `geo` | Google Maps, Mapbox, OpenRouteService |
| Material delivery tracking | `logistics` | WhereParcel, UPS |
| Deal scouting, LLC checks | `property` | AcreLens, OpenCorporates, DistrictAPI |
| Crew time tracking | `productivity` | Clockify |

---

## 2. Fix first — two problems in what we already run

### 2.1 Open-Meteo is licensed non-commercial on the free tier

public-apis lists Open-Meteo as *"Global weather forecast API for **non-commercial use**"*. We call it
from `weather.open_meteo_forecast()` to schedule commercial work, which is outside that grant.

**Fix:** make **NWS (`api.weather.gov`)** the default for anything that touches a job — it is US
government work product, public domain, free, no key, and already wired as `weather nws`. Keep
Open-Meteo for internal//experimental use, or buy the Open-Meteo commercial plan (it is cheap and its
hourly resolution is better than NWS for pour-day decisions).

### 2.2 Geocoding runs entirely on paid keys

`geo` is Google + Mapbox (both metered), and `address` is Smarty (per-lookup). For bulk work — scraping
a PlanHub list, geocoding a county permit dump — that bill scales with row count.

**Fix:** the **Census Geocoder** is already wired (`gov census-geocode`), free, unlimited, and
authoritative for US street addresses. Route batch jobs there and reserve Smarty/Google for the
single-address paths where deliverability and suite-level accuracy actually matter.

Free fallbacks in the list if we outgrow Census: **Nominatim** (no key), **OpenCage**, **Geoapify**,
**Geocod.io** (bulk, appends census tract + school district in one call).

---

## 3. Recommended adds, ranked

### Tier A — build these next

**1. FRED — Federal Reserve Bank of St. Louis** · `apiKey` (free) · *Finance* · **Built** — `market escalation`, `market exposure`
The single highest-leverage add for the estimating toolkit. FRED carries the BLS Producer Price Index
series for lumber, steel mill products, ready-mix concrete, gypsum, and copper wire, plus Census
construction spending and the construction Employment Cost Index.

> Use: escalation clauses and bid-validity windows. Pull the last 12 months of PPI for the divisions
> that dominate a bid, and either justify an escalation allowance with a cited series or shorten bid
> validity from 60 days to 30. This turns "we think material is moving" into a number the estimate
> validator can check.

**2. iLovePDF** · `apiKey` (free 250 docs/month) · *Documents & Productivity* · **Built** — `bidpackage assemble`
Merge, split, extract text, add page numbers. Public bid packages are the use case: an ITB response is
a transmittal + forms + bond + license + insurance + SOV, assembled in a mandated order and paginated.
The FL public-bid work is exactly this, and responsiveness failures are often assembly failures.

**3. Smarty US Extract** · `apiKey` (same Smarty account we already pay for) · *Data Validation*
**Built** — `address extract`. The client method `address.extract_addresses()` already existed; it
had no CLI command, so it was invisible in practice. Pulls postal addresses out of free text —
including emails. Point it at PlanHub/GC bid-invite emails
and it yields a clean job-site address ready for JobTread intake, with no manual retyping and no
copy/paste transposition into the takeoff.

**4. EPA Envirofacts** · No auth · *Government*
**Built** — `site epa`, and folded into `site screen`. The client method
`government.epa_envirofacts()` already existed but was generic and unexposed; the new
`site.epa_facilities()` wraps the Facility Registry Service with the ZIP/city filters we actually
query by. Brownfields, Superfund, underground storage tanks, air and water permits. Screen a parcel
before we price site work or commit to a land deal — a UST or a Superfund boundary is a six-figure
change to a site package and it is free to check.

**5. Nager.Date** · No auth · *Calendar* · **Built** — `schedule working-days`, `schedule add-days`
US public holidays, no key. Working-day math for CPM schedules, draw schedules, and liquidated-damages
counts. Small, but the loan-package and Gantt builders currently have no holiday calendar at all.

### Tier B — high value, narrower trigger

**6. OpenSanctions** · No auth · *Open Data* · **Built** — `compliance vendor` (Vett deferred, see 3.1)
OFAC, PEP, watchlist, and debarment-style screening. On federally funded work we must not contract with
an excluded party. Run every sub and material vendor through this at buyout and keep the response as
the compliance record. Pairs with the FastDOL OSHA/WHD lookup already wired.

**7. Federal Register** · No auth · *Government* · **Built** — `compliance rules`, `compliance register`
The daily journal of the US government. Watch it for Davis-Bacon wage determination changes, new OSHA
rules, and Buy America provisions that change public-bid scope mid-solicitation.

**8. Open Topo Data** · No auth · *Geocoding* · **Built** — `site elevation`
Elevation for a lat/lon. Cut-and-fill sanity checks, finished-floor elevation against base flood
elevation, and drainage direction — a first-pass answer before anyone pays for a survey.

**9. Road511** · `apiKey` · *Transportation* · **Deferred, see 3.1**
Traffic events, cameras, bridges, and **truck routes** across 65 US/CA jurisdictions. For oversize and
overweight deliveries — trusses, tilt panels, crane mobilization — and for maintenance-of-traffic
planning on roadway-adjacent work.

**10. USGS Water Services** · No auth · *Science & Math* · **Built** — `site groundwater`
River stage and groundwater levels. Florida dewatering is a real cost line; groundwater trend plus a
storm forecast tells us whether a foundation pour survives the week.

**11. AQICN / OpenAQ** · `apiKey` · *Weather / Environment* · **Built** — `weather air`
Air quality by location. Dust-control compliance on demolition and site work, and crew-safety calls on
wildfire-smoke days.

**12. Funding Signals** · `apiKey` · *Business* · **Deferred, see 3.1**
Companies that just raised funding, scored as sales leads, from public SEC filings. A funded company
needs space — this is a genuine top-of-funnel source for office and lab tenant-improvement work, which
is the sector where our TI gates already apply.

### 3.1 Deferred, and why

Three picks were left out rather than shipped on a guess. Road511, Funding Signals, and Vett are all
keyed or thinly documented, and this session's egress policy blocks outbound calls to them, so their
request and response contracts could not be verified against the live service. Writing a client to a
contract nobody has confirmed produces code that looks finished and fails on first real use, which
costs more than the integration is worth. Each is a small, self-contained add once someone with a key
can run one live call and confirm the shape.

The same constraint applies to everything that *was* built: the tests are contract tests over mocked
HTTP, not live integration tests. They pin the request we send and the reshaping we do, which is what
catches upstream drift, but the first live call against FRED, iLovePDF, and AQICN should still be
run by someone holding those keys.

### Tier C — only if the trigger exists

- **PVWatts (NREL)** · `apiKey` free — solar production modeling. Worth it only if we bid rooftop PV.
- **Smartcar** · `OAuth` — odometer and location on most new vehicles. Fleet mileage logs and job-site
  arrival times, if the trucks are new enough.
- **NHTSA vPIC** · No auth — VIN decode for the equipment and vehicle schedule on insurance renewals.
- **Climatiq / Carbon Interface** · `apiKey` — embodied carbon by material. Only when an owner or a
  public RFP asks for it; increasingly they do.
- **What3Words** · `apiKey` — three-word coordinates for gate and laydown locations on sites with no
  street address yet.
- **Plaid** · `apiKey` — bank transaction data for cash-flow forecasting against the draw schedule.
  Redundant if QuickBooks already reconciles.

---

## 4. Gaps this list does not fill

public-apis is a general directory, so the Florida-specific sources we depend on are simply not in it.
These are not candidates — they are things we should wire regardless, and they matter more than most of
Tier B:

| Source | Why | Access |
|---|---|---|
| **FEMA National Flood Hazard Layer** | Flood zone, BFE, firm panel — priced into nearly every FL job | Free ArcGIS REST |
| **FL Product Approval + Miami-Dade NOA** | HVHZ envelope compliance; our takeoff skill already demands FL#/NOA | Free portals, no REST API |
| **Florida DBPR license lookup** | Verify sub licensure at buyout | Free portal |
| **Sunbiz (FL Division of Corporations)** | Authoritative FL entity status — free, where OpenCorporates is paid | Free portal |
| **SAM.gov** | Federal exclusions and entity registration for public work | Free API, key required |
| **FDOT** | State road projects, MOT standards, oversize permits | Free |
| **NOAA Tides & Currents** | Coastal/waterfront construction windows | Free API |
| **USDA Web Soil Survey** | Bearing capacity and drainage class before geotech | Free |

---

## 5. Explicitly skipping

- **Project management** (Airtable, Monday, ClickUp, Smartsheet, Asana, Trello) — JobTread is the system
  of record; a second one is a liability.
- **Accounting** (Zoho Books, Front Accounting) — duplicates QuickBooks.
- **EU/UK procurement** (Tenders.guru, UK Companies House, Registrum, OpenMercantil) — wrong geography.
- **Stock/crypto market data** — the Finance category is 90% trading. FRED is the only entry we want.
- **Commodity aggregators** (EconPulse, Sugra) — paid wrappers around data FRED serves free.
- **Carbon offset marketplaces** (Cloverly, CO2 Offset) — offsets, not measurement. Not our scope.

---

## 6. Build order — status

1. ~~Swap the commercial weather default to NWS, and route batch geocoding to the Census geocoder.~~
   **Done** — `weather job` and `geo batch-geocode`. No new keys; removes a licensing exposure and a
   metered bill.
2. ~~Add `market` module — FRED.~~ **Done.** Still open: wire `market escalation` into the estimate
   validator so an escalation allowance is checked against a cited series rather than asserted.
3. ~~Add `bidpackage` module — iLovePDF assembly + Smarty US Extract intake.~~ **Done** —
   `bidpackage assemble` and `address extract`.
4. ~~Add `site` module — EPA Envirofacts, Open Topo Data, USGS Water Services, and FEMA NFHL as one
   "screen this parcel" call.~~ **Done** — `site screen`.
5. ~~Add `compliance` module — OpenSanctions, Federal Register, alongside the existing FastDOL call.~~
   **Done** — `compliance vendor` and `compliance rules`.

Remaining: the estimate-validator hook in step 2, the three deferred integrations in section 3.1, and
the Florida-specific sources in section 4 — of which only FEMA NFHL is currently wired.
