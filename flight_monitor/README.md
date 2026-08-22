# Flight Price Monitor

Monitors flights from **Tampa (TPA)** and **Orlando (MCO)** using the [Ignav API](https://ignav.com).

## Monitors

| Monitor | Route | Schedule | Purpose |
|---------|-------|----------|---------|
| `natal` | → Natal, Brazil | 3× daily | Fixed trip Dec 20 – Feb 15, flexible duration |
| `europe` | → 9 European cities | 1× daily | Deal alerts when great promotions appear |

Both alert **robertavazsantos@gmail.com** and **paulolimad@gmail.com**.

## Quick start

```bash
cd flight_monitor
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
export IGNAV_API_KEY=your_key

.venv/bin/python monitor.py --monitor natal --dry-run
.venv/bin/python monitor.py --monitor europe --dry-run
.venv/bin/python monitor.py --monitor natal          # live
.venv/bin/python monitor.py --monitor europe         # live
```

## Europe deal alerts

- **Destinations:** Lisbon, Madrid, Paris, Rome, London, Amsterdam, Dublin, Barcelona, Frankfurt
- **Dates:** rolling window 45 days – 9 months out
- **Alert when:** price ≤ $2,400 (4 pax) OR new all-time best found
- **Cadence:** once daily (GitHub Actions 14:00 UTC)

## Natal trip

- **Window:** depart Dec 20+, return by Feb 15
- **Duration:** flexible (7–56 nights)
- **Alert when:** ≤ $3,200 or $100+ drop
- **Cadence:** 3× daily

## Configuration

Edit `monitors/natal.yaml` or `monitors/europe.yaml`.

## GitHub setup

Secret: `IGNAV_API_KEY`

Workflows:
- `.github/workflows/flight-monitor.yml` — Natal
- `.github/workflows/flight-monitor-europe.yml` — Europe deals
