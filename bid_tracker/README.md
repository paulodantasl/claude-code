# Bid Tracker — Public Construction Bidding Tracker & Submittal Prep

Runs weekly, finds public solicitations that fit your company, and for each
qualified opportunity builds a ready-to-work folder with the basic info, the
solicitation documents, a requirements & submittal checklist, and a
**first-draft proposal**.

---

## What it does

```
┌──────────────────────────────────────────────────────────────────────────┐
│                              BID TRACKER                                    │
│                                                                            │
│  ┌────────────┐   ┌──────────────────┐   ┌───────────────────────────┐    │
│  │  Sources   │   │   Qualifier      │   │   Bid Packager            │    │
│  │  SAM.gov   │──▶│  bid/no-bid      │──▶│  per-opportunity folder:  │    │
│  │  RSS feeds │   │  criteria score  │   │   • summary               │    │
│  │  Portals   │   │  (0–100)         │   │   • requirements checklist│    │
│  │  (AI read) │   └──────────────────┘   │   • submittal checklist   │    │
│  └────────────┘            │             │   • downloaded documents  │    │
│        │                   ▼             │   • FIRST-DRAFT proposal   │    │
│        │           ┌──────────────┐      │   • cover letter          │    │
│        │           │  SQLite DB   │      └───────────────────────────┘    │
│        │           │ (dedupe/log) │              │                         │
│        ▼           └──────────────┘              ▼                         │
│  ┌──────────────────────────────────────────────────────────────────┐    │
│  │  Alerts: console / Slack / email for each new qualified bid        │    │
│  └──────────────────────────────────────────────────────────────────┘    │
└──────────────────────────────────────────────────────────────────────────┘
```

1. **Pull** open solicitations from each configured source (last 7 days).
2. **Qualify** each against your criteria — NAICS, project keywords, geography,
   contract value, bonding capacity, set-asides, and response window.
3. **Store** new records in SQLite (so each weekly run only surfaces new bids).
4. **Package** every qualified opportunity into its own folder.
5. **Alert** the team.

### Sources supported

| Type | When to use | Needs |
|---|---|---|
| `sam_gov` | Federal opportunities (nationwide or by state) | free `SAM_GOV_API_KEY` |
| `rss` | State/local portals that publish an RSS/Atom feed | nothing |
| `ai` | Agency portals with no API or feed | `ANTHROPIC_API_KEY` |

### Claude is optional

With `ANTHROPIC_API_KEY` set, Claude reads non-standard portals, extracts
structured submission requirements from solicitation text, and writes a tailored
proposal draft. Without it, the system still runs and falls back to
template-based requirements and proposals — so a usable draft always lands in
the folder.

---

## Quick start

```bash
cd bid_tracker
pip install -r requirements.txt
cp .env.example .env          # add SAM_GOV_API_KEY (and ANTHROPIC_API_KEY)
```

Then edit the three config files for your company:

- `targets/criteria.yaml` — your bid/no-bid criteria (NAICS, states, value range, …)
- `targets/sources.yaml` — which portals/feeds to track
- `company/profile.yaml` — firm info used in the proposal & cover letter

Run it:

```bash
# Weekly run across all sources (last 7 days)
python -m bid_tracker run

# See what qualifies without writing folders
python -m bid_tracker run --dry-run

# Specific sources, 14-day lookback, with Slack alerts
python -m bid_tracker run --source sam_gov --days 14 --slack-webhook $SLACK_WEBHOOK_URL

# Run continuously, once a week
python -m bid_tracker watch --interval 7d

# List configured sources / export qualified bids
python -m bid_tracker sources
python -m bid_tracker export --output qualified.csv
```

---

## What lands in each package folder

```
bid_packages/2026-07-01_W912EP-26-B-0001_runway-repair/
├── 00_OPPORTUNITY_SUMMARY.md     # who/what/where/when + why it qualified
├── 01_REQUIREMENTS_CHECKLIST.md  # forms, bonds, insurance, eval criteria
├── 02_SUBMITTAL_CHECKLIST.md     # tick-box list to complete before submitting
├── 03_PROPOSAL_DRAFT.md          # first-draft proposal (Claude or template)
├── 04_COVER_LETTER.md            # cover letter populated from company profile
├── opportunity.json              # machine-readable record + qualification
└── documents/                    # downloaded solicitation attachments
```

---

## Running weekly, automatically

**Option A — GitHub Actions** (included): `.github/workflows/bid-tracker-weekly.yml`
runs every Monday. Add `SAM_GOV_API_KEY`, `ANTHROPIC_API_KEY`, and
`SLACK_WEBHOOK_URL` as repository secrets. Note: GitHub Actions runners are
ephemeral, so commit the resulting packages/DB as an artifact or point
`DATABASE_URL` at a hosted database for persistent dedupe.

**Option B — cron** on a server:

```cron
0 7 * * 1  cd /path/to/bid_tracker && /usr/bin/python -m bid_tracker run >> run.log 2>&1
```

**Option C — `watch` mode**: `python -m bid_tracker watch --interval 7d`.

---

## Coverage (out of the box)

`targets/sources.yaml` ships pre-populated with **45 sources**: SAM.gov (federal)
plus the procurement portal of every county and incorporated city in the Tampa
Bay region — Citrus, Hernando, Hillsborough, Manatee, Pasco, Pinellas — and Lee
County and its cities. Each entry points at that agency's real bid-listing page
(OpenGov, Bonfire/Euna, DemandStar, IonWave, ProcureWare, BidNet, or a CivicPlus
Bids page), with the hosting platform noted in a comment.

`targets/criteria.yaml` is tuned for **small construction work, $0–$300K, in
Florida** — `max_value` is enforced as a hard cap, so anything larger is
disqualified.

## Notes & limitations

- The SAM.gov adapter is fully functional against the public v2 API.
- Most local portals serve their public bid-listing page, which the `ai` source
  reads via Claude. Some platforms gate full solicitation **documents** behind a
  free vendor registration — listings are still visible. Requests use a
  browser User-Agent since these sites block default bot agents.
- Portal URLs were researched June 2026; if an agency migrates platforms, update
  its `listing_url`. The small Pinellas barrier-island towns and tiny Pasco
  municipalities are noted in the YAML and can be enabled if needed.
- Proposal drafts are **first drafts**. Every firm-specific gap is marked
  `[PLACEHOLDER: …]`; review before submitting. The drafter is instructed not to
  invent licenses, dollar figures, or past projects.
