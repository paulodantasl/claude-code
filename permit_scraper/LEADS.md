# Issued-Permit Lead Generation → GC & Owner Outreach

Scan the municipal portals for permits that reach **Issued** status and turn each
one into a **sales lead**: a project you can pitch, with the **general contractor
of record** and the **owner** as your two contacts. Output is a dated **CSV
call-list** (and, optionally, a **Google Sheet**).

> A permit hitting *Issued* means the job is real, funded, and about to build —
> the ideal moment to offer your services to the GC or owner.

This is a third, distinct workflow in `permit_scraper/`:

| Workflow | Question it answers | Command |
|---|---|---|
| Discovery pipeline | "Where is Amazon/Publix building?" (new big-company permits) | `run` / `watch` |
| Monitoring ([MONITORING.md](MONITORING.md)) | "Did *my* permit change status?" | `monitor` |
| **Lead gen (this doc)** | "Which projects just got issued that I can pitch?" | `leads` |

---

## How it works

```
counties.yaml ─▶  for each county: scrape recent permits
leads.yaml ─────▶  keep only ISSUED + in-scope (commercial/residential projects)
                   drop trade noise (re-roofs, water heaters, …) + sub-floor $$
dedupe store ───▶  drop anything already surfaced  ➜  only NEW leads
                        │
                        ▼
            CSV call-list  (+ optional Google Sheet)
            one row per project · GC contact · owner contact
```

- **Only new leads each run** — a JSON dedupe store means a permit becomes a lead
  exactly once, no matter how often you scan. No database required.
- **Contacts come straight off the permit** — GC name + license, owner name +
  mailing address (the Accela detail parser now captures these; other fields are
  recovered from the raw record when present). No third-party lookups.

---

## Quick start

```bash
cd permit_scraper
pip install -r requirements.txt

# Tune what counts as a lead (categories, $ floors, recency, noise filter)
$EDITOR targets/leads.yaml

# One scan of the last 30 days → appends new leads to permit_leads.csv
python -m permit_scraper leads

# Scan specific counties, last 14 days, and also push to Google Sheets
python -m permit_scraper leads --county pasco_county hillsborough_county --days 14 --google-sheet

# Run it on a schedule (every 24h)
python -m permit_scraper leads --interval 24h
```

Prove the engine end-to-end (no browser / network / DB):

```bash
python -m permit_scraper.leads.demo
```

---

## Scope & filtering — `targets/leads.yaml`

```yaml
leads:
  include_categories: [commercial, residential, industrial]
  qualifying_phases: [issued]          # add "inspections" for under-construction jobs
  issued_within_days: 45               # freshness gate (null = off)
  min_value:                           # per-category floors (omit a category = no floor)
    commercial: 100000
    residential: 150000
    industrial: 250000
  exclude_keywords: []                 # empty = use the built-in trade-noise list
```

**How a permit is categorised** — from its type + description keywords:
`industrial` (warehouse, distribution, data center…) → `residential` (SFR, dwelling,
townhome, new home…) → `commercial` (retail, office, restaurant, TI, shell…).

**Noise filtering** — standalone trade / low-value permits (re-roof, water heater,
HVAC change-out, window, fence, pool, sign, solar, demolition-only, etc.) are
dropped by default. A permit whose scope *also* names real project work ("New
Construction", "Addition", "Alteration", "Tenant Improvement", "Shell") is **kept**
even if it mentions a trade word. Edit `exclude_keywords` to tune, or set
`min_value` to gate on dollars.

---

## The CSV call-list

One row per new issued permit, columns ordered for working the phones
top-to-bottom:

`issued_date, permit_number, category, county_name, project_address, city,
zip_code, permit_type, description, estimated_value, total_sqft,` **`gc_name,
gc_license, gc_phone,`** **`owner_name, owner_mailing_address, owner_phone,`**
`applicant_name, parcel_number, portal_url, lead_status, first_seen, …`

Import it straight into your CRM, or share the Google Sheet with the sales team.

---

## What you get, and the honest limits

- **GC of record** — name + state license number come off the permit reliably on
  Accela portals; a phone appears only when the portal lists one.
- **Owner** — name + mailing address when the permit exposes them.
- **Phones/emails are often absent** on the permit itself. You chose "permit
  fields only" to ship fast — the natural next step is enrichment: look up the
  contractor's license on **FL DBPR (MyFloridaLicense)** for a business phone, and
  the owner's mailing address via the **county property appraiser** (the package
  already has property-appraiser scrapers). That can be layered on without
  changing this pipeline.
- **Issue-date coverage** depends on the portal. API sources (Socrata / ArcGIS)
  can filter precisely by issue date; the browser scrapers search by application
  date, so the dedupe store (not the date window) is what guarantees you never
  work the same lead twice.

---

## Scheduling

Same options as monitoring — pick one:

```bash
# built-in loop
python -m permit_scraper leads --interval 24h
```
```cron
# cron: daily at 6am
0 6 * * * cd /opt/permit_scraper && /usr/bin/python3 -m permit_scraper leads >> /var/log/permit_leads.log 2>&1
```
A systemd timer / launchd job running `python -m permit_scraper leads` works the
same way (see MONITORING.md for a timer template).

---

## Compliance note

Permit data is public record, but outreach is regulated. Before cold-calling or
texting GCs/owners from this list, make sure your campaign follows TCPA/DNC rules
(and email CAN-SPAM). This tool builds the list; it's on you to contact people
lawfully.
