# No-code alternative: Zapier email parser → JobTread

Same architecture as the Python bridge — XactAnalysis's own notification email
is the trigger — but assembled from hosted pieces. Use this if you'd rather
not run a script anywhere.

## Pieces

- **Email Parser by Zapier** (parser.zapier.com) — gives you an
  `xxxx@robot.zapier.com` address and a point-and-click template trainer.
- **JobTread's Zapier app** — first-class integration with actions for
  creating customers, jobs, etc. (<https://www.jobtread.com/integrations/zapier>)

## Setup

1. Complete the XactAnalysis notification setup in
   [`XACTANALYSIS_SETUP.md`](XACTANALYSIS_SETUP.md) — but add the
   `@robot.zapier.com` parser address as the notification recipient (or have
   your dedicated inbox auto-forward to it; forwarding your own mail is fine).
2. In Email Parser, open the first received assignment email and highlight the
   fields you want: claim number, insured name, loss address, phone, peril,
   carrier, adjuster. Save the template.
3. Create a Zap:
   - **Trigger:** Email Parser — New Email
   - **Action:** JobTread — Create Customer (map insured name/phone)
   - **Action:** JobTread — Create Job (map claim number + peril into the job
     name, everything else into the description; set your New Lead stage if
     the action exposes it)
4. Add a **Filter** step after the trigger requiring the claim-number field to
   be non-empty — this skips non-assignment mail if anything else ever lands
   in the parser address.
5. Turn the Zap on and send a test.

## Trade-offs vs. the Python bridge

| | Zapier | Python bridge (this repo) |
|---|---|---|
| Hosting | none | cron/VPS/office PC |
| Cost | monthly, per-task | $0 |
| Parser robustness | template-based; can silently mis-parse when a carrier's template differs | defensive regexes + full-body fallback into the job description |
| Dedupe | manual (add a "find job" search step) | built-in (message ID + claim number) |
| Change control | click-ops | code-reviewed in this repo |

Reasonable path: start with Zapier this week, switch to the Python bridge if
volume makes the Zapier bill annoying or a carrier's template breaks the
point-and-click parser.
