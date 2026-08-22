---
name: flight-monitor
description: Monitor TPA/MCO flights to Natal (3x daily) and Europe deal alerts (1x daily). Alerts to robertavazsantos@gmail.com and paulolimad@gmail.com.
---

# Flight Monitor

## Monitors

| ID | What | Cadence |
|----|------|---------|
| `natal` | TPA/MCO → Natal, Dec 20–Feb 15, flexible stay | 3×/day |
| `europe` | TPA/MCO → 9 EU cities, deal hunting | 1×/day |

```bash
cd flight_monitor && export IGNAV_API_KEY=...
python monitor.py --monitor natal --dry-run
python monitor.py --monitor europe
```

## Alerts

Both monitors notify **only**:
- robertavazsantos@gmail.com
- paulolimad@gmail.com

Europe: alert on ≤ $2,400 (4 pax) or any new best price.
Natal: alert on ≤ $3,200 or $100+ drop.

Draft emails — never send without Paulo's approval.
