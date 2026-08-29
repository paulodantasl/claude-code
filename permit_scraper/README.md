# Permit Scraper — Agentic Early Intelligence for Commercial Building Permits

Get ahead of the market by tracking new commercial and industrial building permit applications
before news breaks. Know where the next Publix, Amazon warehouse, or data center will open.

> **Two related workflows built on the same scrapers:**
> - **[MONITORING.md](MONITORING.md)** — watch your *own* pending permits for
>   **status updates** and text the assigned **field manager**
>   (`python -m permit_scraper monitor`).
> - **[LEADS.md](LEADS.md)** — catch permits the moment they're **issued** and
>   turn each into a **sales lead** (GC of record + owner) as a CSV call-list /
>   Google Sheet (`python -m permit_scraper leads`).
>
> Both differ from the discovery pipeline below, which finds *new* big-company
> permits by watch-list.

---

## How It Works

```
┌─────────────────────────────────────────────────────────────────────┐
│                         PERMIT SCRAPER                              │
│                                                                     │
│  ┌──────────────┐    ┌────────────────────┐    ┌─────────────────┐ │
│  │  County      │    │   Scraper Layer    │    │  AI Agent       │ │
│  │  Config      │───▶│  Socrata API       │    │  (Claude)       │ │
│  │  (YAML)      │    │  Accela Portal     │    │                 │ │
│  └──────────────┘    │  OpenGov Portal    │───▶│  Navigate any   │ │
│                      └────────────────────┘    │  portal via     │ │
│  ┌──────────────┐              │               │  Playwright     │ │
│  │  Watch List  │              ▼               └─────────────────┘ │
│  │  (companies) │    ┌────────────────────┐              │        │
│  └──────────────┘    │  Raw Permits       │◀─────────────┘        │
│          │           └────────────────────┘                        │
│          │                    │                                     │
│          ▼                    ▼                                     │
│  ┌──────────────────────────────────┐                              │
│  │  Classifier (fuzzy match)        │                              │
│  │  "Vadata Inc" → Amazon (96%)     │                              │
│  │  "Publix Super Markets" → Publix │                              │
│  └──────────────────────────────────┘                              │
│                    │                                                │
│                    ▼                                                │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────────┐ │
│  │  SQLite /    │  │  Slack Alert │  │  CSV Export              │ │
│  │  PostgreSQL  │  │  Email Alert │  │                          │ │
│  └──────────────┘  │  Webhook     │  └──────────────────────────┘ │
│                    └──────────────┘                                 │
└─────────────────────────────────────────────────────────────────────┘
```

### Three scraping strategies — automatically selected

| Strategy | When used | How |
|---|---|---|
| **Socrata Open Data API** | County publishes on data.cityofXYZ.gov | Direct JSON API with SoQL date filters |
| **Rule-based browser** | Standard Accela / OpenGov portals | Playwright fills forms, paginates results |
| **AI Agent (Claude)** | Non-standard or complex portals | Claude navigates the UI step-by-step via screenshots + DOM |

---

## Quick Start

### 1. Install

```bash
cd permit_scraper
pip install -r requirements.txt
playwright install chromium
```

### 2. Configure

```bash
cp .env.example .env
# Edit .env — add ANTHROPIC_API_KEY at minimum
```

### 3. Run

```bash
# Scrape all configured counties (last 7 days)
python -m permit_scraper run

# Scrape Miami-Dade + Broward, last 30 days, alert to Slack
python -m permit_scraper run \
  --county miami_dade broward \
  --days 30 \
  --slack-webhook $SLACK_WEBHOOK_URL

# Use the AI agent for a non-standard portal
python -m permit_scraper run --county palm_beach --ai-agent

# Run continuously every 24 hours
python -m permit_scraper watch --interval 24h

# Export all matches to CSV
python -m permit_scraper export --output matches.csv

# List all configured counties
python -m permit_scraper counties
```

---

## Configuration

### Adding a County (`targets/counties.yaml`)

```yaml
targets:
  # Socrata open-data portal (simplest — no login required)
  - id: my_county
    name: "My County"
    state: FL
    type: socrata
    open_data_url: "https://opendata.mycounty.gov/resource/permits.json"
    open_data_type: socrata

  # Accela Citizen Access portal
  - id: my_city
    name: "My City"
    state: GA
    type: accela
    base_url: "https://permits.mycity.gov/CitizenAccess"

  # Force AI agent (for non-standard or complex portals)
  - id: hard_portal
    name: "Hard Portal County"
    state: TX
    type: accela
    base_url: "https://epermits.hardportal.gov"
    use_ai_agent: true
```

### Adding Companies to Watch (`targets/companies.yaml`)

```yaml
watch_list:
  - id: my_retailer
    display_name: "My Retailer"
    aliases:
      - "My Retailer Inc"
      - "My Retailer LLC"
      - "MRI Properties"          # holding company / subsidiary
    permit_types: ["commercial", "retail", "new construction"]
    min_value: 500000
```

### Alert Channels

Configure in `.env` or pass flags to the CLI:

| Channel | Config |
|---|---|
| Console (default) | Always enabled |
| Slack | `SLACK_WEBHOOK_URL=https://hooks.slack.com/...` |
| Email | `SMTP_HOST`, `SMTP_USER`, `SMTP_PASS` |
| CSV | `--csv-output matches.csv` |
| Webhook | Set `type: webhook` + `url` in alert_channels |

---

## How the AI Agent Works

For complex portals (CAPTCHAs, heavy JavaScript, non-standard UIs), the AI agent
uses an **observe → think → act** agentic loop powered by Claude:

```
1. Take screenshot of the portal
2. Send screenshot + task description to Claude
3. Claude uses tools to interact:
   - click(selector)
   - type_text(selector, text)
   - navigate(url)
   - extract_permits(html)   ← calls Claude Haiku to parse HTML
   - done(permits)           ← ends the loop
4. Repeat until all pages are extracted
```

The agent automatically handles:
- Dynamic form filling (date pickers, dropdowns)
- JavaScript-rendered content
- Pagination
- Detail page extraction

To enable for a specific county, add `use_ai_agent: true` to its config, or pass
`--ai-agent` to the CLI.

---

## Database Schema

All data is stored in SQLite (default) or PostgreSQL.

```
permits
  id, source_id, county_id, county_name
  permit_number, permit_type, status, description
  applicant_name, owner_name, contractor_name
  address, city, state, zip_code, parcel_number, lat, lon
  estimated_value, total_sqft
  filed_date, issued_date
  matched_company_id, matched_company_name, match_score
  alert_sent, source_url, scraped_at, raw_data

scraper_runs
  county_id, scraper_type, started_at, finished_at
  records_found, records_new, records_matched, status
```

---

## Data Sources Reference

| Platform | Coverage | API? | Notes |
|---|---|---|---|
| Socrata | NYC, LA, Houston, Dallas, King County | ✓ JSON | Best option — free, no auth |
| Accela | Miami-Dade, Broward, Palm Beach, Orange County FL, many more | Partial | REST API requires county approval |
| OpenGov | Fulton County GA, growing | Partial | React SPA — intercepted API calls |
| Property Appraiser | Florida counties (BCPA, MDPA, PBCPA) | Varies | Cross-reference permits with property owner |

---

## Tips for Finding Amazon, Publix, etc.

1. **Shell companies**: Amazon often files permits under "Vadata Inc" or "Amazon Data
   Services". Publix uses "Publix Super Markets Inc" or "Publix Realty". Add these to
   `companies.yaml`.

2. **Look at contractors**: The GC (general contractor) on the permit is often a
   national firm (Whiting-Turner, Brasfield & Gorrie) that works exclusively with
   specific retailers. A $5M warehouse permit by Whiting-Turner in an industrial park
   is almost certainly Amazon.

3. **Estimated value thresholds**: Set `min_value` to filter noise. A new Publix is
   typically $3–8M; an Amazon fulfillment center is $30–100M+.

4. **Cross-reference with property appraiser**: After finding a permit, look up the
   parcel in the property appraiser system to see who recently bought the land.

5. **Zoning applications**: Commercial rezoning often precedes permit applications by
   6–18 months. Consider adding zoning board agendas to your scraper targets.

---

## Project Structure

```
permit_scraper/
├── scrapers/
│   ├── base.py              # Abstract BaseScraper + RawPermit dataclass
│   ├── accela.py            # Accela Citizen Access (Playwright + REST API)
│   ├── opengov.py           # OpenGov portal (Playwright)
│   └── socrata_api.py       # Socrata open data API
├── agents/
│   ├── permit_agent.py      # Claude agentic loop for complex portals
│   └── classifier.py        # Fuzzy company matching
├── targets/
│   ├── counties.yaml        # County/city scraper configs
│   └── companies.yaml       # Company watch list with aliases
├── storage/
│   ├── models.py            # SQLAlchemy models
│   └── database.py          # DB init + session management
├── notifications/
│   └── alerts.py            # Console / email / Slack / webhook / CSV
├── monitoring/              # ── Permit-update monitoring (see MONITORING.md) ──
│   ├── monitor.py           #   Orchestrator: fetch → diff → notify → persist
│   ├── differ.py            #   Detects meaningful status changes
│   ├── status.py            #   Normalises portal statuses → lifecycle phases
│   ├── notifier.py          #   Instant field-manager alerts (SMS/Slack/email/…)
│   ├── state_store.py       #   JSON snapshot store + JSONL event log (no DB)
│   ├── fetchers.py          #   Live-scraper / injectable current-state fetchers
│   ├── config.py            #   Loads + validates tracked/managers/counties
│   └── demo.py              #   End-to-end self-test (no browser/network/DB)
├── leads/                   # ── Issued-permit lead generation (see LEADS.md) ──
│   ├── pipeline.py          #   Scan issued permits → dedupe → enrich → CSV/Sheet
│   ├── classifier.py        #   Qualify issued+in-scope permits; build GC/owner lead
│   ├── models.py            #   Lead + LeadConfig
│   ├── store.py             #   JSON dedupe store + JSONL lead history
│   ├── exporters.py         #   CSV call-list + Google Sheet export
│   ├── enrichment/          #   Contact enrichment (opt-in)
│   │   ├── dbpr.py          #     GC via FL DBPR (data-file or web)
│   │   ├── appraiser.py     #     Owner mailing via county property appraiser
│   │   ├── manager.py       #     Orchestration + persistent cache + rate limit
│   │   └── base.py          #     Enricher interface, result merge, cache
│   └── demo.py              #   End-to-end self-test (no browser/network/DB)
├── targets/
│   ├── tracked_permits.yaml #   Pending permits to monitor for updates
│   ├── field_managers.yaml  #   Who gets notified, and on which channels
│   └── leads.yaml           #   Lead scope: categories, $ floors, noise filter
├── pipeline.py              # Main orchestration (discovery)
├── main.py                  # CLI (click) — run / watch / export / monitor / tracked / leads
├── requirements.txt
├── MONITORING.md            # Guide for the permit-update monitoring feature
├── LEADS.md                 # Guide for issued-permit lead generation
└── .env.example
```
