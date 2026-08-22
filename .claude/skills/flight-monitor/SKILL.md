---
name: flight-monitor
description: Monitor Tampa/Orlando to Natal Brazil flight prices for 4 passengers (2A+2C). Flexible dates Dec 20–Feb 15 — finds cheapest departure/return combo regardless of duration.
---

# Flight Monitor — TPA/MCO → Natal

## When to use

Track the **cheapest round-trip** from **Tampa (TPA)** or **Orlando (MCO)** to **Natal (NAT)** for **2 adults + 2 children**.

**Date window:** depart on or after **Dec 20**, return by **Feb 15**. Duration is **flexible** — the search tries many stay lengths (7–56 nights) and refines around the lowest prices.

## Run a check

```bash
cd flight_monitor
pip install -r requirements.txt
export IGNAV_API_KEY=your_key
python monitor.py --dry-run     # preview queries
python monitor.py               # adaptive search (12 queries)
python monitor.py --explore     # deeper search (24 queries)
python monitor.py --json
```

## How the search works

1. **Coarse grid** — samples departures every 4 days × multiple stay lengths across the full window
2. **Refine** — when a cheap combo is found, searches ±3 days around those dates
3. **Rotate** — each scheduled run explores a different slice so coverage builds over time
4. **Best overall** — stored in `data/prices.db`; alerts on new lows

## Credentials

`IGNAV_API_KEY` — sign up at https://ignav.com

## Alerts

- `target_price_usd: 3200`
- `notify_emails`: robertavazsantos@gmail.com, paulolimad@gmail.com only
- Draft emails — do not send without Paulo's approval
