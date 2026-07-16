# Permit-Update Monitoring → Instant Field-Manager Notifications

Automatically re-checks a watch-list of **pending residential and commercial
permits** on municipal portals (Accela and others), detects **status changes**
run-over-run, and sends **instant notifications to the assigned field manager**
the moment a permit moves.

> **How this differs from the discovery pipeline.** The `run` / `watch` commands
> *discover new* big-company commercial permits and skip residential + anything
> already seen. Monitoring is the mirror image: you already know the permit
> number (it's *your* project), and you want to be paged when **its status
> changes** — application → plan review → corrections → issued → inspections →
> CO. Residential is fully supported here.

---

## What it does, in one pass

```
tracked_permits.yaml ─┐
field_managers.yaml ──┼─▶  PermitMonitor.run_once()
counties.yaml ────────┘         │
                                ├─ 1. fetch current state of each permit
                                │     (one portal hit per county)
                                ├─ 2. diff vs. last-known snapshot on disk
                                ├─ 3. on change → build event, notify the
                                │     assigned manager(s) instantly
                                └─ 4. save new snapshot + append to event log
```

- **No false alarms on day one.** The first time a permit is seen it is
  *baselined silently*; you only get pinged on subsequent *changes*
  (override with `--notify-first-seen`).
- **Idempotent.** A change fires exactly once — the snapshot advances after it's
  detected. Re-running is safe.
- **No database required.** State is a single JSON file; the event log is JSONL.
  Drop it on a cron host, a laptop, or a Pi in the job trailer.

---

## Quick start

```bash
cd permit_scraper
pip install -r requirements.txt          # yaml + requests are all the monitor needs
cp .env.example .env                      # add SMS / SMTP / Slack creds you plan to use

# 1. List the permits you're tracking (ships with examples — replace them)
$EDITOR targets/tracked_permits.yaml
$EDITOR targets/field_managers.yaml

# 2. One pass (prints notifications to the console; nothing sent yet if dry-run)
python -m permit_scraper monitor --dry-run

# 3. For real, once:
python -m permit_scraper monitor

# 4. Run continuously, checking every 30 minutes:
python -m permit_scraper monitor --interval 30m

# 5. See last-known status of everything you track:
python -m permit_scraper tracked
```

Prove the whole engine works on your machine (no browser, network, or DB):

```bash
python -m permit_scraper.monitoring.demo
```

---

## Configuration

### `targets/tracked_permits.yaml` — the permits you're watching

```yaml
tracked_permits:
  - permit_number: "BD-2025-028100"      # required — the portal's record number
    county: pasco_county                 # required — must match an id in counties.yaml
    project_name: "Publix — Angeline Town Center"
    address: "3400 Angeline Blvd, Land O Lakes, FL 34638"
    category: commercial                 # residential | commercial | industrial
    managers: [msmith, ops_desk]         # field_managers.yaml ids to notify
    watch_fields: [next_inspection]      # optional extra portal fields to watch
```

### `targets/field_managers.yaml` — who gets notified, and how

```yaml
field_managers:
  - id: msmith
    name: "Marcus Smith"
    phone: "+18135550122"                # E.164, for SMS
    email: "marcus@example.com"
    slack_webhook: "https://hooks.slack.com/services/…"   # optional per-manager
    channels: [sms, slack]               # fired in order; each one independent
```

Channels: `console`, `sms`, `slack`, `email`, `webhook`. A manager can have any
combination. Secrets live in `.env` / environment variables — never in YAML.

### `targets/counties.yaml` — portal configs (shared with the scraper)

Already populated for Central & Central-West Florida. Each tracked permit's
`county` must be an `id` here so the monitor knows which portal + scraper to use.

---

## How "current state" is fetched

Grouped by county, so each portal is hit once per pass. Per portal type:

| Portal | Lookup strategy |
|---|---|
| **Accela (API)** | Direct `GET /records?customId=<permit#>` — exact, cheap. |
| **Accela (browser)** | Searches the Citizen Access page by record number, parses the detail page; falls back to a bulk scan if the search UI differs. |
| **Socrata / ArcGIS / EnerGov / OpenGov / CityView** | Universal fallback: one bulk scrape over `--lookback-days`, indexed by permit number (separator-insensitive) with an address fallback. |

A permit that can't be found this run (portal down, wrong number) is reported as
`missing` and its snapshot is left untouched — never a spurious "changed" alert.

You can also bypass scrapers entirely and feed state from your own system by
passing a custom fetcher to `PermitMonitor` (see `monitoring/fetchers.py`).

---

## Status phases & priority

Raw portal labels ("Plan Review", "In Review", "Corrections Required", "CO
Issued"…) are normalised to lifecycle **phases**:

`submitted → in_review → approved → issued → inspections → finaled`
plus `action_required`, `denied`, `expired`, `withdrawn`.

- **HIGH priority** (⚠️ ACTION REQUIRED): `action_required`, `denied`, `expired`
  — corrections, holds, resubmittal requests, denials. These are what a field
  manager most needs same-day.
- **Normal** (🔔): everything else, including good-news milestones (issued,
  finaled).

Notifications also state the **direction** of movement (advanced / moved back /
needs attention). Add a jurisdiction's oddball wording by editing the keyword
rules in `monitoring/status.py` — no engine changes needed.

---

## Scheduling ("regularly checks")

Pick one. The built-in loop is simplest; a system scheduler is more robust.

**Built-in watch loop**
```bash
python -m permit_scraper monitor --interval 30m
```

**cron** (every 30 min)
```cron
*/30 * * * * cd /opt/permit_scraper && /usr/bin/python3 -m permit_scraper monitor >> /var/log/permit_monitor.log 2>&1
```

**systemd timer** (`/etc/systemd/system/permit-monitor.service` + `.timer`)
```ini
# permit-monitor.service
[Service]
Type=oneshot
WorkingDirectory=/opt/permit_scraper
EnvironmentFile=/opt/permit_scraper/.env
ExecStart=/usr/bin/python3 -m permit_scraper monitor

# permit-monitor.timer
[Timer]
OnCalendar=*:0/30
Persistent=true
[Install]
WantedBy=timers.target
```

**macOS launchd** — a `StartInterval` of `1800` running the same module works
identically.

---

## State & audit trail

- `permit_monitor_state.json` — last-known snapshot per permit (what the diff
  compares against). Written atomically. Delete it to re-baseline everything.
- `permit_monitor_state.json.events.jsonl` — append-only log of every detected
  change and every notification attempt (per channel, success/failure). This is
  your audit trail — grep it, ship it to a SIEM, load it into a sheet.

Override the path with `--state-file`.

---

## Reliability notes

- Notifications are **best-effort per channel**: one failing channel (bad SMS
  gateway) never blocks the others, and every attempt is recorded on the event.
- If *every* channel fails for a permit, `PermitMonitor` can hold the snapshot
  back so the next pass retries (`advance_snapshot_on_notify_failure=False`).
  The default advances (avoids duplicate storms); failures are visible in the
  run summary and event log.
- The `--watch` loop never dies on a single bad pass — it logs and continues.

---

## Testing

`python -m permit_scraper.monitoring.demo` runs four scenarios end-to-end with
canned portal responses (no browser / network / DB) and asserts:

1. First pass baselines silently; second pass detects real changes.
2. HIGH-priority flagging for corrections/denials.
3. Multi-channel routing hits the right manager on the right channel.
4. The shipped example YAML configs load and validate.

Exit code `0` = all green.
