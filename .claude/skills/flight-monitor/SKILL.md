---
name: flight-monitor
description: Monitor Tampa/Orlando to Natal Brazil flight prices for 4 passengers (2 adults, 2 children), Dec 20–Jan 30 departures, 14+ night stays. Run 3x daily.
---

# Flight Monitor — TPA/MCO → Natal

## When to use

Paulo wants to track the best round-trip airfare from **Tampa (TPA)** or **Orlando (MCO)** to **Natal, RN, Brazil (NAT)** for **2 adults + 2 children**, departing between **December 20 and January 30**, staying **at least 14 nights**.

## Run a check

```bash
cd flight_monitor
pip install -r requirements.txt
python monitor.py --dry-run    # preview queries
python monitor.py              # live search (needs AMADEUS_API_KEY + AMADEUS_API_SECRET)
python monitor.py --json         # machine-readable output
```

## Credentials

Requires Amadeus API keys in environment (or GitHub secrets for Actions):

- `AMADEUS_API_KEY`
- `AMADEUS_API_SECRET`
- `AMADEUS_ENV` — `test` (sandbox) or `production` (real fares)

Register free: https://developers.amadeus.com/register

## Scheduled monitoring

**GitHub Actions** (preferred for 24/7): `.github/workflows/flight-monitor.yml` runs at 12:00, 18:00, and 00:00 UTC.

**Cursor timer** (for this Cloud Agent session):

Use `subscribe_timer` with cron `0 12,18,0 * * *` and prompt:

> Run the Natal flight monitor: `cd flight_monitor && pip install -q -r requirements.txt && python monitor.py`. Report the best price found. If alert_triggered in JSON output, summarize the deal and draft an email to robertavazsantos@gmail.com and paulolimad@gmail.com only. Do not send without approval.

## Alerts

Configured in `flight_monitor/config.yaml`:

- `target_price_usd: 3200` — notify when total ≤ $3,200
- `drop_threshold_usd: 100` — notify on $100+ improvement
- `notify_emails`:
  - robertavazsantos@gmail.com
  - paulolimad@gmail.com

When alerting, send **only** to those two addresses. Draft first — do not send without explicit approval.

## Output interpretation

- `best_this_run` — cheapest fare found in the current check
- `all_time_best` — lowest price ever recorded in `data/prices.db`
- `booking_link` — Google Flights URL for manual verification

## Adjusting dates or party

Edit `flight_monitor/config.yaml`:

- `departure_anchors` — which departure dates to rotate through
- `season.min_stay_days` — minimum nights (default 14)
- `passengers.adults` / `passengers.children`

## Troubleshooting

| Problem | Fix |
|---------|-----|
| `missing_credentials` | Set Amadeus API keys |
| No offers returned | Try `AMADEUS_ENV=production`; NAT is a small airport — connections are normal |
| Test prices look fake | Switch to production Amadeus environment |
| Rate limits | Reduce `search.max_queries_per_run` in config |
