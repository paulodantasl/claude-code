# Flight Price Monitor — Tampa/Orlando → Natal, Brazil

Monitors round-trip airfare for **4 passengers (2 adults + 2 children)** from **Tampa (TPA)** or **Orlando (MCO)** to **Natal (NAT)**.

**Flexible date search:** finds the cheapest combination of departure and return within **December 20 – February 15**. Trip length is not fixed — the agent tries multiple durations (7–56 nights) and refines around the best prices found.

Runs **3 times per day** via GitHub Actions (or on demand).

## Quick start

### 1. Get Ignav API key (free)

1. Sign up at [ignav.com](https://ignav.com)
2. Copy your API key from the dashboard
3. Add GitHub repository secret: `IGNAV_API_KEY`
4. For local runs: `cp .env.example .env` and paste the key

### 2. Run locally

```bash
cd flight_monitor
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
export IGNAV_API_KEY=your_key_here

# Preview planned queries
.venv/bin/python monitor.py --dry-run

# Live search (adaptive — 12 queries)
.venv/bin/python monitor.py

# Deeper exploration (24 queries)
.venv/bin/python monitor.py --explore

# JSON output
.venv/bin/python monitor.py --json
```

### 3. GitHub Actions schedule

Workflow: `.github/workflows/flight-monitor.yml`

| UTC cron | ~Eastern time |
|----------|---------------|
| 12:00    | 8:00 AM       |
| 18:00    | 2:00 PM       |
| 00:00    | 8:00 PM       |

Trigger manually: **Actions → Flight Price Monitor → Run workflow**

## Configuration

Edit `config.yaml`:

| Setting | Default | Description |
|---------|---------|-------------|
| `season.departure_start` | 2026-12-20 | Earliest departure |
| `season.latest_return` | 2027-02-15 | Latest return date |
| `season.min_stay_days` | 7 | Shortest trip considered |
| `search.departure_step_days` | 4 | Coarse grid spacing |
| `search.stay_lengths` | 7–56 nights | Durations tried per departure |
| `passengers` | 2 adults, 2 children | Party size |
| `alerts.target_price_usd` | 3200 | Alert when total ≤ this |
| `alerts.drop_threshold_usd` | 100 | Alert on $100+ drop vs best |
| `alerts.notify_emails` | robertavazsantos@gmail.com, paulolimad@gmail.com | Alert recipients |

Date combinations rotate across runs so all anchor departures get covered over time without exceeding API limits.

## Price history

SQLite database: `flight_monitor/data/prices.db`

Cached in GitHub Actions between runs. Artifacts uploaded per run (90-day retention).

## Cursor Cloud Agent

Use the skill at `.claude/skills/flight-monitor/SKILL.md` to run checks from a Cloud Agent.

## Notes

- Uses [Ignav](https://ignav.com) — 1,000 free requests, then pay-per-use
- TPA/MCO → NAT typically requires connections (GRU, GIG, FOR). Prices vary by date.
- Google Flights links generated for each result for manual verification
- Amadeus self-service was decommissioned July 2026; Ignav replaced it
