# ideal-apis

Unified Python client and CLI for Ideal Construction Tier 1 & 2 public API integrations.

## Install

```bash
cd ideal_apis
pip install -e .
```

Copy `.env.example` to `.env` (repo root or `ideal_apis/.env`) and add API keys for paid services. Many integrations are free and work without keys.

## Quick start

### Python

```python
from ideal_apis import IdealAPIs

api = IdealAPIs()

# Free — dental leads (NPPES)
dentists = api.leads.dentists_tampa_bay(limit=10)

# Free — Tampa weather forecast
forecast = api.weather.open_meteo_forecast(27.9506, -82.4572)

# Free — federal construction spend in FL
awards = api.government.usaspending_florida_construction(limit=10)

# Keyed — validate address before JobTread intake
validated = api.address.validate("401 E Jackson St", "Tampa", "FL", "33602")
```

### CLI

```bash
ideal-api list                  # all commands
ideal-api list --tier 1         # tier 1 only
ideal-api keys                  # which keys are configured

ideal-api call leads dentists --limit 5
ideal-api call weather forecast --lat 27.9506 --lon -82.4572
ideal-api call gov usaspending --limit 5
ideal-api call validation email --email office@theidealremodeling.com
ideal-api call web microlink --url https://idealcgc.com

# Added for construction workflows — all keyless except market
ideal-api call site screen --lat 27.9506 --lon -82.4572 --zip 33602
ideal-api call compliance vendor --name "Example Construction LLC"
ideal-api call schedule working-days --start 2026-09-01 --end 2026-12-31
ideal-api call weather job --lat 27.9506 --lon -82.4572
ideal-api call market escalation --series construction_materials --months 12
```

## Escalation in the estimate validator

`market.bid_exposure()` feeds `estimating/scripts/refresh_escalation.py`, which writes a
committed snapshot that `validate_estimate.py` reads on every run — so every bid is
checked against a current, cited index without a key or network at validation time. A
scheduled workflow keeps the snapshot fresh and opens an issue when materials move.
See [the estimating README](../estimating/README.md#escalation-check-automatic).

## Weather licensing

Use `weather job` (NWS) for anything that touches a real job. Open-Meteo's free tier
is licensed for non-commercial use only, so `weather.open_meteo_forecast()` is kept
for internal and experimental work. NWS is US government work product in the public
domain and carries no such restriction.

## Geocoding cost

`gov census-geocode` and `geo batch-geocode` are free, keyless, and unlimited. Route
bulk work — scraped PlanHub lists, county permit dumps — through them, and reserve
Google, Mapbox, and Smarty for single-address paths where deliverability and
suite-level accuracy actually matter.

## Services

| Module | Tier | Key APIs | Typical use |
|--------|------|----------|-------------|
| `address` | 1 | Smarty | Normalize job-site addresses for JobTread |
| `validation` | 1 | Numverify, Kickbox, EVA | Phone/email hygiene before QUO |
| `leads` | 1 | NPPES, Yelp, CMS | Dental/commercial lead gen |
| `permits` | 1 | Socrata, Data.gov | Permit intel (complements `permit_scraper`) |
| `weather` | 1 | NWS, Open-Meteo, NOAA hail, RainViewer | Scheduling, storm/restoration leads |
| `government` | 1 | USAspending, Federal Contracts, FastDOL, Census | Public bids, sub vetting |
| `web` | 1 | Microlink | Bid page / listing metadata |
| `documents` | 2 | DocStruct, OCR.Space, BuildPDF, PandaDoc | Invoices, COIs, proposals |
| `geo` | 2 | Google Maps, Mapbox, OpenRouteService | Drive time, isochrones |
| `logistics` | 2 | WhereParcel, UPS | Material delivery tracking |
| `property` | 2 | AcreLens, OpenCorporates, DistrictAPI | Deal scouting, LLC checks |
| `productivity` | 2 | Clockify | Crew time tracking |
| `market` | 1 | FRED | Material/labor escalation, bid validity |
| `site` | 1 | Open Topo Data, FEMA NFHL, USGS, EPA | Parcel screening before pricing site work |
| `compliance` | 1 | OpenSanctions, Federal Register | Sub/vendor screening, public-work rule changes |
| `schedule` | 1 | Nager.Date | Working-day math for CPM, draws, LDs |
| `bidpackage` | 2 | iLovePDF | Bid package assembly and pagination |

## Florida Socrata permit endpoints

Use with `ideal-api call permits socrata --endpoint URL --days 7`:

- Hillsborough: check Data.gov catalog via `ideal-api call permits fl-datasets --county Hillsborough`
- Pinellas, Orange, etc.: same pattern — endpoint URLs live in county open-data portals

Your existing `permit_scraper` Socrata adapter can share `IDEAL_SOCRATA_APP_TOKEN`.

## What to build next

See [`API-CANDIDATES.md`](./API-CANDIDATES.md) for the ranked review of the
[public-apis](https://github.com/paulodantasl/public-apis) directory this work came from. Tier A,
most of Tier B, and both licensing/cost fixes are now built; that doc tracks what remains and the
Florida-specific sources the directory does not carry.

## Notes

- NWS (`api.weather.gov`) requires a descriptive `User-Agent` — set via `IDEAL_USER_AGENT`.
- NOAA hail uses the free SWDI NEXRAD endpoint (no key).
- Keyed APIs raise `MissingAPIKeyError` with the env var name if credentials are absent.
