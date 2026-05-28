# JobTread weekly monitor

Scheduled GitHub Actions workflow that queries the JobTread Pave API,
renders an at-a-glance PNG dashboard per configured job, and emails the
PNGs to a recipient list via Gmail SMTP.

- Source: `scripts/jobtread_monitor/monitor.py`
- Workflow: `.github/workflows/jobtread-weekly-monitor.yml`

The dashboard adapts to the job state:

- **Active jobs** show schedule progress %, delay-risk callout (red, capslocked),
  budget watch flags, and top items.
- **Closed jobs** show realized margin, fully-paid status, and a green
  "JOB CLOSED" banner instead of a fake delay risk.

KPI row order: Contract Value → Schedule → Actual Cost → Margin
(so actual cost sits between schedule and margin for at-a-glance
margin control).

---

## One-time setup

You need to give the workflow three secrets and (optionally) two repo
variables. All values stay in GitHub; nothing is committed.

### 1. Generate a JobTread Pave grant key

1. Log into JobTread as an admin of your organization.
2. Go to **Settings → Pave / API access** (exact menu name may vary).
3. Create a new grant key with read access to jobs, documents, tasks,
   files and comments.
4. Copy the key.

### 2. Generate a Gmail app password

The script sends through Gmail SMTP, which requires an app password
(not your regular Gmail password) because Google disabled basic auth.

1. Make sure 2-Step Verification is on for the sending Gmail account.
2. Visit <https://myaccount.google.com/apppasswords>.
3. Create an app password labeled "JobTread monitor". Copy the 16-char
   value (Google shows it with spaces; you can paste with or without).

### 3. Add the secrets to this repo

In GitHub:

`Settings → Secrets and variables → Actions → New repository secret`

Add three secrets:

| Name                  | Value                                     |
| --------------------- | ----------------------------------------- |
| `JOBTREAD_GRANT_KEY`  | The Pave grant key from step 1            |
| `GMAIL_USER`          | The sending Gmail address                 |
| `GMAIL_APP_PASSWORD`  | The 16-char app password from step 2      |

### 4. (Optional) Override the job list and recipient

Same screen, **Variables** tab → New repository variable:

| Name           | Default                            | Example                            |
| -------------- | ---------------------------------- | ---------------------------------- |
| `MAIL_TO`      | `office@theidealremodeling.com`    | `pm@example.com,ops@example.com`   |
| `JOB_NUMBERS`  | `2026-343,2026-336`                | `2026-343,2026-336,2026-360`       |

Updating the variable does **not** require a code change — the next
workflow run picks up the new value.

---

## How to run it

### Scheduled (default)

The workflow is configured to run every Monday at **12:00 UTC**, which
is **8:00 AM Eastern Daylight Time** most of the year (and 7:00 AM
during EST, Nov–Mar). If you want a different time, edit the cron
expression in `.github/workflows/jobtread-weekly-monitor.yml`.

### On demand

Go to **Actions → JobTread Weekly Monitor → Run workflow**. You can
also pass a one-off `dry_run: true` to render the PNGs as workflow
artifacts without sending email.

### Locally (for testing)

```bash
cd scripts/jobtread_monitor
pip install -r requirements.txt
export JOBTREAD_GRANT_KEY=...   # required
export GMAIL_USER=you@gmail.com # required unless DRY_RUN=1
export GMAIL_APP_PASSWORD=...   # required unless DRY_RUN=1
export JOB_NUMBERS=2026-343,2026-336
export DRY_RUN=1                # skip SMTP; just render PNGs to /tmp/jobtread
python monitor.py
```

PNGs land in `/tmp/jobtread/JobTread_<NUMBER>_dashboard_<DATE>.png`.

---

## Customizing

- **Add/remove jobs**: change the `JOB_NUMBERS` repo variable.
- **Change recipient**: change the `MAIL_TO` repo variable.
- **Different schedule**: edit the `cron:` line in the workflow.
- **Dashboard layout**: edit `render_dashboard()` in `monitor.py`.
- **What counts as "delay risk"**: edit `overdue_tasks()` in `monitor.py`.
  Current rule: any non-group task with `endDate < today` and progress
  < 100% is treated as overdue.

---

## Notes & limitations

- **No diff tracking yet.** "What Changed" shows current observations,
  not week-over-week deltas. Adding a state file (uploaded/downloaded
  as a workflow artifact each run) would enable real diffs.
- **Job numbering.** The monitor matches jobs by their JobTread
  `number` field exactly. Make sure the values in `JOB_NUMBERS` match
  how they appear in JobTread.
- **Gmail rate limits.** Gmail SMTP allows ~500 emails/day for free
  accounts. One email per job per week is well under this.
- **Container fonts.** The workflow installs `fonts-dejavu-core` so
  PIL has the same fonts the renderer expects.
