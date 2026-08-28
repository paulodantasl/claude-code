# `estimating/data/`

Machine-written inputs the estimating scripts read. Nothing here is hand-edited.

## `escalation.json`

A snapshot of trailing material price movement, read by
`validate_estimate.py` on every run to check the contingency a bid carries against
what a published index actually did.

**It is not in the repository yet.** It is written by:

```bash
python3 estimating/scripts/refresh_escalation.py     # needs IDEAL_FRED_KEY
```

and refreshed automatically each month by the `escalation-monitor` workflow, which
commits the result. Until the first refresh runs, the validator reports one INFO row
saying the snapshot is missing and continues — no failure, no fabricated number.

That absence is deliberate. A seeded placeholder would be indistinguishable from real
index data once it reached an estimate, and a bid defended by a made-up series is
worse than a bid with no escalation check at all. Every figure the validator prints
traces to a FRED observation with a date and a value, or it does not print.

### Setup

1. Get a free API key at <https://fred.stlouisfed.org/docs/api/api_key.html>.
2. For local runs: add `IDEAL_FRED_KEY=...` to `.env`.
3. For the scheduled workflow: add it as the `IDEAL_FRED_KEY` repository secret.
   Without it the workflow fails loudly rather than committing an empty snapshot.
