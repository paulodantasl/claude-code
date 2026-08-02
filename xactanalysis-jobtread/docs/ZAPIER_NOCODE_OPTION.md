# Zapier setup runbook: XactAnalysis email → JobTread lead

Same safe architecture as the Python bridge — XactAnalysis's own notification
email is the trigger, nothing ever logs into the Verisk portal — but built
from hosted pieces so nothing runs on your hardware. Follow this top to
bottom; total hands-on time is about 30–45 minutes.

## What you need before starting

- [ ] A Zapier account (zapier.com — free tier is fine to build and test;
      multi-step Zaps need a paid plan to stay on)
- [ ] JobTread login with permission to connect integrations
- [ ] XactAnalysis admin login (one manual visit, to add a notification
      recipient — see step 2)

---

## Step 1 — Create the parser mailbox (5 min)

1. Go to <https://parser.zapier.com> and sign in with your Zapier account.
2. Click **Create Mailbox**. You'll get an address like
   `xa-claims@robot.zapier.com`. Copy it.
3. Leave the tab open — it will say "waiting for an email."
4. Send it a training email now so you can build the template before any real
   claim arrives: copy the entire contents of
   [`../tests/sample_emails/sample_assignment.txt`](../tests/sample_emails/sample_assignment.txt)
   into an email, subject
   `XactAnalysis New Assignment - Claim ABC-2026-0421337`, and send it to the
   parser address from any account.

## Step 2 — Point XactAnalysis at the parser address (10 min, manual portal visit)

Do the notification setup in
[`XACTANALYSIS_SETUP.md`](XACTANALYSIS_SETUP.md), with one choice to make:

- **Option A (simplest):** add the `…@robot.zapier.com` address directly as a
  notification recipient for New Assignment events.
- **Option B (recommended):** add `claims@theidealremodeling.com` as the
  recipient, then set that mailbox to auto-forward to the parser address.
  You keep a permanent archive of every notification in a mailbox you own,
  and if you ever switch off Zapier (e.g. to the Python bridge in this repo)
  you only change the forwarding rule, not the Verisk config.

Either way, XactAnalysis is only ever sending email — nothing automated
touches the portal.

## Step 3 — Train the parser template (10 min)

1. Back in parser.zapier.com, open the training email from step 1.
2. Highlight each value and name the field. Use these exact names — the Zap
   mappings below refer to them:

   | Highlight this in the email | Field name |
   |---|---|
   | `ABC-2026-0421337` (after "Claim Number:") | `claim_number` |
   | `Jane Q. Sample` | `insured_name` |
   | `(727) 555-0142` | `phone` |
   | `4821 Example Ave N` + the city line below it | `loss_address` |
   | `Water` | `type_of_loss` |
   | `07/28/2026` | `date_of_loss` |
   | `$2,500.00` | `deductible` |
   | `Example Mutual Insurance` | `carrier` |
   | `HO-99182734` | `policy_number` |
   | `Alex Casefile` | `adjuster_name` |
   | `(800) 555-0100` | `adjuster_phone` |
   | `acasefile@examplemutual.test` | `adjuster_email` |

3. Save the template.
4. **When the first real assignment email arrives**, open it in the parser's
   history, check every field parsed correctly, and re-highlight/save if the
   carrier's template differs from the sample. Repeat once per new
   carrier/program — after that it's hands-off.

## Step 4 — Build the Zap (15 min)

Create a new Zap with these steps in order:

**1. Trigger — Email Parser by Zapier → New Email**
   - Mailbox: the one from step 1.
   - Test: it should pull in the training email with all fields populated.

**2. Filter by Zapier**
   - Only continue if… `claim_number` — *(Text) Exists*.
   - This is the guard that keeps stray mail (out-of-office bounces,
     newsletters, anything else that reaches the parser address) from ever
     becoming a lead.

**3. Action — JobTread → Create Customer**
   - Connect your JobTread account when prompted (OAuth — you approve it
     once; Zapier stores the connection).
   - Name: `insured_name` (fallback: type `Claim` + `claim_number` if you
     want a name even when parsing misses the insured).
   - Phone/email: map `phone` if the action exposes contact fields.

**4. Action — JobTread → Create Job** *(exact action names in the JobTread
   Zapier app may differ slightly, e.g. Create Job/Create Location; pick the
   one that creates the job under the customer from step 3)*
   - Customer/Account: **Use the ID output by step 3** (choose "Custom" and
     select the previous step's ID field — don't pick a fixed customer from
     the dropdown).
   - Job name: `Claim {{claim_number}} — {{insured_name}} — {{type_of_loss}}`
   - Address/location: `loss_address`
   - Description — paste this block and map the fields into it:

     ```
     New lead auto-created from XactAnalysis assignment notification.

     Claim number: {{claim_number}}
     Insured: {{insured_name}}
     Phone: {{phone}}
     Loss address: {{loss_address}}
     Carrier: {{carrier}}
     Type of loss: {{type_of_loss}}
     Date of loss: {{date_of_loss}}
     Policy number: {{policy_number}}
     Deductible: {{deductible}}
     Adjuster: {{adjuster_name}} — {{adjuster_phone}} — {{adjuster_email}}

     --- Original notification ---
     {{body_plain}}
     ```

     (`body_plain` is the parser's built-in full-body field — including it
     means even a mis-parsed email still delivers all its information into
     the lead.)
   - Stage/status: if your JobTread org tracks pipeline in a field the action
     exposes, set it to your **New Lead** stage here.

**5. (Optional) Action — Slack / SMS / email notification** to whoever runs
   sales, with the job link, so a human sees every new lead land.

Name the Zap `XactAnalysis → JobTread new lead` and turn it on.

## Step 5 — End-to-end test (5 min)

1. Forward the sample training email to the parser address again **but first
   change the claim number** (e.g. `ABC-2026-TEST01`) so it reads as a new
   claim.
2. Watch the Zap run (Zap History) and confirm a customer + job appear in
   JobTread with all fields.
3. Delete the test customer/job in JobTread.
4. When the next real assignment arrives, verify once more against real data.

## Duplicates

XactAnalysis normally sends one notification per new assignment, so
duplicates are rare. If a carrier program re-sends notifications (status
updates, reminders) to the same address:

- tighten the Filter step (e.g. subject *(Text) Contains* `New Assignment`), or
- add a **JobTread → Find Job** search step before Create Customer, searching
  the claim number, with "Skip if found" behavior.

## Cost and when to switch off Zapier

Every claim consumes 2–4 Zapier tasks. At low claim volume the Starter plan
is fine; if the bill grows past what a $5/mo VPS costs, move to the Python
bridge in this repo — the XactAnalysis side doesn't change at all (especially
if you chose Option B in step 2: just remove the auto-forward and point the
bridge at the same mailbox).
