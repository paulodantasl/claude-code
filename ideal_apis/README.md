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
```

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

## Florida Socrata permit endpoints

Use with `ideal-api call permits socrata --endpoint URL --days 7`:

- Hillsborough: check Data.gov catalog via `ideal-api call permits fl-datasets --county Hillsborough`
- Pinellas, Orange, etc.: same pattern — endpoint URLs live in county open-data portals

Your existing `permit_scraper` Socrata adapter can share `IDEAL_SOCRATA_APP_TOKEN`.

## Notes

- NWS (`api.weather.gov`) requires a descriptive `User-Agent` — set via `IDEAL_USER_AGENT`.
- NOAA hail uses the free SWDI NEXRAD endpoint (no key).
- Keyed APIs raise `MissingAPIKeyError` with the env var name if credentials are absent.

## Automated daily pipeline

Run the full lead workflow (NPPES → OpenFEMA → weather → gov intel → ledger → CSV):

```bash
ideal-api daily
ideal-api daily --skip-yelp          # if no IDEAL_YELP_KEY yet
ideal-api daily --push-jobtread      # needs JOBTREAD_GRANT_KEY in .env
ideal-api daily --push-jobtread --live   # actually create JobTread accounts
```

Outputs land in `ideal_apis/data/output/`:

- `daily_leads_YYYY-MM-DD.json` — all new rows
- `jobtread_import_YYYY-MM-DD.csv` — contactable leads for CRM import
- `summary_YYYY-MM-DD.md` — email-ready digest

Dedupe state: `ideal_apis/data/leads_ledger.json`

Edit sources in `ideal_apis/config/pipeline.yaml` (cities, taxonomies, brands).

### JobTread auto-push

Add to `.env`:

```
JOBTREAD_GRANT_KEY=your_grant_key
```

Then:

```bash
ideal-api daily --push-jobtread --live
```

Without the grant key, the pipeline still runs and writes the CSV — import manually or let a Cursor agent use JobTread MCP.
