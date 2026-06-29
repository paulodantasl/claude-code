# Job Application Review System

Find, score, and tailor government job applications for **Pasco, Hillsborough,
and Pinellas counties (FL)** — then review and submit them yourself.

It scrapes openings from [governmentjobs.com](https://www.governmentjobs.com)
(NEOGOV), compares each posting against your **resume + LinkedIn**, drafts
tailored application materials for the strong matches, and flags them in a
review queue. **It never submits an application on its own** — a human (you)
always reviews and submits.

---

## How it works

```
  profile/                      targets/agencies.yaml
  ├─ resume.pdf                 (Pasco / Hillsborough / Pinellas
  └─ linkedin.pdf                cities + counties on NEOGOV)
        │                                  │
        ▼                                  ▼
  ┌───────────────────────────────────────────────────────────┐
  │  JobReviewPipeline                                         │
  │                                                            │
  │  1. Scrape   governmentjobs.com career portals            │
  │              (JSON fast-path → HTML parse → AI agent)      │
  │  2. Score    lexical gate → Claude semantic fit (0–100)    │
  │  3. Tailor   cover letter + resume bullets + answers       │
  │              (grounded only in YOUR real experience)       │
  │  4. Flag     write packet, alert, add to review queue      │
  └───────────────────────────────────────────────────────────┘
        │
        ▼
  Review queue  ──►  you edit the draft  ──►  YOU submit
        │
        └─ optional: `prefill` opens the browser, logs in,
           fills the form, and STOPS at the submit screen.
```

The human-in-the-loop boundary is the whole point: the system gets you to a
ready-to-submit application and stops.

---

## Quick start

```bash
cd job_reviewer
pip install -r requirements.txt
playwright install chromium          # only needed for the `prefill` browser assist

cp .env.example .env                 # add your ANTHROPIC_API_KEY (and govjobs login if you want prefill)
```

1. **Add your profile.** Drop your resume (and optionally a LinkedIn PDF export)
   into `profile/`. See [`profile/README.md`](profile/README.md). For example:
   ```bash
   cp "~/Desktop/Paulo Dantas Resume jun26.pdf" profile/resume.pdf
   ```

2. **Verify the agency portals load** (slugs can vary):
   ```bash
   python -m job_reviewer agencies
   ```
   Open each printed URL once and confirm it shows that employer's jobs. Fix any
   slug that 404s in `targets/agencies.yaml`.

3. **Run the pipeline:**
   ```bash
   python -m job_reviewer run                       # all three counties
   python -m job_reviewer run --county pinellas      # one county
   python -m job_reviewer run --no-ai                # lexical only, no API cost
   ```

4. **Review what got flagged:**
   ```bash
   python -m job_reviewer queue --min-score 60
   python -m job_reviewer export --csv queue.csv --markdown queue.md
   ```
   Draft application packets are written to `packets/*.md`.

5. **(Optional) browser pre-fill** — logs into your account, fills the form,
   and **stops before submit**:
   ```bash
   python -m job_reviewer prefill --job-id <id-from-queue>
   ```

6. **Track your decisions:**
   ```bash
   python -m job_reviewer mark <job-id> submitted     # or: reviewed | dismissed
   ```

---

## Commands

| Command | What it does |
|---|---|
| `agencies` | List configured employers + their career-portal URLs to verify |
| `run` | Scrape → score → tailor → flag jobs for review |
| `queue` | Show the review queue, ranked by fit score |
| `export` | Write the queue to CSV / Markdown |
| `prefill` | Open browser, log in, pre-fill an application, stop before submit |
| `mark` | Update a job's review status (reviewed / submitted / dismissed) |

Run `python -m job_reviewer <command> --help` for options.

---

## Configuration

- **Agencies** — `targets/agencies.yaml`. Add/remove employers; each maps to a
  `governmentjobs.com/careers/{slug}` portal. Per-agency CSS `selectors:` can be
  overridden if a portal's markup differs.
- **Profile** — `profile/` (resume + LinkedIn). Optional `profile.yaml` for
  structured overrides (titles, skills, keywords, target salary).
- **Environment** — `.env` (see `.env.example`): `ANTHROPIC_API_KEY`,
  optional `GOVJOBS_USERNAME`/`GOVJOBS_PASSWORD` for prefill, optional Slack/SMTP
  alert channels, `DATABASE_URL`.

---

## Design notes & boundaries

- **Never auto-submits.** The system prepares and flags; you submit. The browser
  assist defaults to a visible window and hard-stops at the review screen.
- **No fabrication.** Tailored materials are grounded only in your real resume /
  LinkedIn — the model is instructed never to invent employers, titles, degrees,
  or metrics.
- **Credentials stay local.** Your governmentjobs.com login is read from your
  environment and used only to log into governmentjobs.com. It is never stored,
  logged, or transmitted elsewhere. Your resume, LinkedIn, drafts, and database
  are all gitignored.
- **Be a good citizen.** Scraping is rate-limited (1 req/s per agency) and reads
  only public postings. This is a personal assistant for your own applications,
  not a bulk auto-applier — respect governmentjobs.com's Terms of Service.
- **Slugs need a one-time check.** NEOGOV career-portal slugs aren't fully
  predictable; `agencies` lists them all so you can verify in a minute.

---

## Architecture

```
job_reviewer/
├─ main.py                 # Click CLI
├─ pipeline.py             # orchestration
├─ scrapers/
│  ├─ base.py              # RawJob + BaseJobScraper
│  └─ governmentjobs.py    # NEOGOV scraper (JSON → HTML → detail enrich)
├─ profile_loader/         # parse resume + LinkedIn (pdf/docx/txt)
├─ matching/               # lexical gate + Claude semantic fit scoring
├─ tailor/                 # cover letter + bullets + answer drafting
├─ agents/                 # Playwright + Claude browser pre-fill (stops at submit)
├─ review/                 # review queue (CSV / Markdown export)
├─ notifications/          # Slack / email "flagged for review" alerts
├─ storage/                # SQLAlchemy models + SQLite
├─ targets/agencies.yaml   # Pasco / Hillsborough / Pinellas employers
└─ profile/                # ← your resume + LinkedIn (gitignored)
```
