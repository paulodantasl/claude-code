# XactAnalysis → JobTread New-Lead Bridge

Automatically turn every new XactAnalysis claim assignment into a JobTread lead —
**without ever automating against Verisk's systems**, which is what got the
account blocked last time.

## Why the account was blocked (and what this changes)

Verisk's XactAnalysis terms of use prohibit bots, scrapers, and any automated
login to the portal. Their bot detection flags headless browsers and scripted
sessions, and repeat offenses can get an account terminated permanently — which
would cut off claim assignments entirely. So this project deliberately contains
**zero code that touches xactanalysis.com**. No Selenium, no scraping, no stored
portal credentials.

Instead, it uses the one data channel Verisk pushes to you automatically and
officially: **assignment notification emails**. XactAnalysis already emails the
qualified contractor contact every time a new assignment arrives. This bridge
watches a dedicated mailbox you own, parses each notification, and creates the
lead in JobTread through JobTread's public Open API. Reading your own email is
fully within both vendors' terms.

```
XactAnalysis ──(official notification email)──► claims@yourdomain
                                                      │
                                     this service (IMAP poll, read-only)
                                                      │
                              parse claim #, insured, loss address, peril
                                                      │
                          JobTread Pave API ──► Customer + Location + Job (lead)
```

## Your options, ranked

| # | Option | Cost | Effort | Verisk risk |
|---|--------|------|--------|-------------|
| 1 | **Email-notification bridge (this repo)** | $0 | Configure a mailbox + run this service | None — Verisk sends the email to you |
| 2 | **Zapier no-code version of #1** | Zapier plan | ~1 hour, no code | None |
| 3 | **Official Verisk third-party export (EDI/XML)** | Verisk/partner fees | Contact your Xactware rep | None — it's their sanctioned channel |
| 4 | Portal scraping / auto-login | — | — | **Account ban. Do not do this again.** |

Details, trade-offs, and sources for each are in
[`docs/INTEGRATION_OPTIONS.md`](docs/INTEGRATION_OPTIONS.md).

> **Current status:** rolling out **option 2 first** — follow the step-by-step
> runbook in [`docs/ZAPIER_NOCODE_OPTION.md`](docs/ZAPIER_NOCODE_OPTION.md).
> The Python bridge below stays ready as the $0 replacement if Zapier's
> per-task cost becomes annoying; the XactAnalysis notification setup is
> identical for both.

## Quick start (option 1)

1. **XactAnalysis side (one-time, done by a human in the portal):** add a
   notification rule that emails every *New Assignment* event to a dedicated
   inbox such as `claims@theidealremodeling.com`. Steps in
   [`docs/XACTANALYSIS_SETUP.md`](docs/XACTANALYSIS_SETUP.md).
2. **JobTread side:** create an API grant key (Settings → Integrations →
   JobTread API) and note your organization ID.
3. **Configure:** `cp .env.example .env` and fill in the IMAP and JobTread
   values.
4. **Install & test:**

   ```bash
   pip install -r requirements.txt
   python -m src.main --once --dry-run   # parse pending emails, print leads, create nothing
   python -m src.main --once             # process pending emails for real
   python -m src.main                    # run continuously (poll every 5 min)
   ```

5. Run it under cron/systemd/a small VPS. State lives in `state.json` so
   restarts never duplicate a lead.

If you'd rather not run any code, follow
[`docs/ZAPIER_NOCODE_OPTION.md`](docs/ZAPIER_NOCODE_OPTION.md) — same
architecture, built from Zapier's Email Parser and the first-class JobTread
Zapier app.

## What gets created in JobTread

For each new assignment email:

- **Customer** account named after the insured
- **Location** with the loss address
- **Job** named `Claim <number> — <insured> — <peril>`, with the full parsed
  claim details (carrier, adjuster, date of loss, deductible, contacts) in the
  job description, ready for your New Lead pipeline stage

Every email is archived to `processed/` and deduplicated by both message ID and
claim number, so forwarded copies or carrier re-sends don't create doubles.

## Layout

```
xactanalysis-jobtread/
├── README.md                    ← you are here
├── docs/
│   ├── INTEGRATION_OPTIONS.md   ← all safe options + why scraping fails
│   ├── XACTANALYSIS_SETUP.md    ← portal notification setup (manual, one-time)
│   └── ZAPIER_NOCODE_OPTION.md  ← no-code alternative
├── src/
│   ├── main.py                  ← entry point / poll loop
│   ├── config.py                ← env-based configuration
│   ├── email_client.py          ← IMAP fetch (your inbox, not Verisk's)
│   ├── parser.py                ← assignment-email field extraction
│   ├── jobtread.py              ← JobTread Pave API client
│   └── state.py                 ← dedupe store
├── tests/
│   ├── test_parser.py
│   └── sample_emails/
├── .env.example
└── requirements.txt
```
