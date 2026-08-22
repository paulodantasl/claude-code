# Flight Price Monitor — Tampa/Orlando → Natal, Brazil

Monitors round-trip airfare for **4 passengers (2 adults + 2 children)** from **Tampa (TPA)** or **Orlando (MCO)** to **Natal (NAT)**, with departures between **December 20 and January 30** and a **minimum 14-night stay**.

Runs **3 times per day** via GitHub Actions (or on demand).

## Quick start

### 1. Get Amadeus API credentials (free)

1. Register at [developers.amadeus.com](https://developers.amadeus.com/register)
2. Create an app and copy **API Key** and **API Secret**
3. Add them as GitHub repository secrets:
   - `AMADEUS_API_KEY`
   - `AMADEUS_API_SECRET`
4. Optional: set repository variable `AMADEUS_ENV` to `production` for live fares (default is `test` sandbox)

### 2. Run locally

```bash
cd flight_monitor
pip install -r requirements.txt
cp .env.example .env   # fill in keys

# Preview which date/origin combos will be searched
python monitor.py --dry-run

# Live search
python monitor.py

# JSON output
python monitor.py --json
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
| `season.departure_end` | 2027-01-30 | Latest departure |
| `season.min_stay_days` | 14 | Minimum trip length |
| `passengers` | 2 adults, 2 children | Party size |
| `alerts.target_price_usd` | 3200 | Alert when total ≤ this |
| `alerts.drop_threshold_usd` | 100 | Alert on $100+ drop vs best |
| `alerts.notify_emails` | robertavazsantos@gmail.com, paulolimad@gmail.com | Alert recipients |

Date combinations rotate across runs so all anchor departures get covered over time without exceeding API limits.

## Price history

SQLite database: `flight_monitor/data/prices.db`

Cached in GitHub Actions between runs. Artifacts uploaded per run (90-day retention).

## Cursor Cloud Agent

Use the skill at `.claude/skills/flight-monitor/SKILL.md` to run checks from a Cloud Agent, or set up timer subscriptions:

```
subscribe_timer name=flight-monitor-morning cron="0 12 * * *"
subscribe_timer name=flight-monitor-afternoon cron="0 18 * * *"
subscribe_timer name=flight-monitor-evening cron="0 0 * * *"
```

## Notes

- Amadeus **test** environment returns sample data; use **production** keys for real prices.
- TPA/MCO → NAT typically requires connections (often via GRU, GIG, or FOR). Prices vary widely by date.
- Google Flights links are generated for each result for manual price verification.
- Children are ages 2–11 per Amadeus API rules.
