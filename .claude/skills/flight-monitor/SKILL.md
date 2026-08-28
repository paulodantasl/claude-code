---
name: flight-monitor
description: Monitor Tampa/Orlando to Natal Brazil flight prices for 4 passengers (2 adults, 2 children), Dec 20–Jan 30 departures, 14+ night stays. Run 3x daily via Ignav API.
---

# Flight Monitor — TPA/MCO → Natal

## When to use

Track round-trip airfare from **Tampa (TPA)** or **Orlando (MCO)** to **Natal, RN, Brazil (NAT)** for **2 adults + 2 children**, departing **December 20 – January 30**, staying **at least 14 nights**.

## Run a check

```bash
cd flight_monitor
pip install -r requirements.txt
export IGNAV_API_KEY=your_key
python monitor.py --dry-run    # preview queries
python monitor.py              # live search
python monitor.py --json         # machine-readable output
```

## Credentials

Requires `IGNAV_API_KEY` in environment (or GitHub secret `IGNAV_API_KEY` for Actions).

Sign up free: https://ignav.com

## Scheduled monitoring

**GitHub Actions**: `.github/workflows/flight-monitor.yml` runs at 12:00, 18:00, and 00:00 UTC.

**Cursor timer** prompt:

> Run the Natal flight monitor: `cd flight_monitor && pip install -q -r requirements.txt && IGNAV_API_KEY=$IGNAV_API_KEY python monitor.py --json`. Report best price. If alert_triggered, draft email ONLY to robertavazsantos@gmail.com and paulolimad@gmail.com. Do not send without approval.

## Alerts

Configured in `flight_monitor/config.yaml`:

- `target_price_usd: 3200`
- `drop_threshold_usd: 100`
- `notify_emails`: robertavazsantos@gmail.com, paulolimad@gmail.com

## Troubleshooting

| Problem | Fix |
|---------|-----|
| `missing_credentials` | Set `IGNAV_API_KEY` |
| No offers | NAT is a small airport — connections are normal |
| Rate limits | Reduce `search.max_queries_per_run` in config |
