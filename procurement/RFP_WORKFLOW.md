# RFP Workflow

The process the procurement agent follows to run vendor bidding on a project.
Repeatable across projects — the only project-specific inputs are the JobTread
Job ID and the Drive folder that holds the plans.

## Steps

### 1. Bootstrap the plans folder

Runs once per project, before any RFPs go out.

1. Locate the JobTread Job's linked Google Drive root (the JobTread↔Drive sync
   creates one automatically at project creation).
2. Inside the root, create — or verify — a folder named `_BID_SET/`. This is
   the canonical name; do not vary it.
3. Populate `_BID_SET/` with the current *Issued for Construction* plan set:
   architectural, structural, MEP, civil, and any specs/details vendors need to
   bid. Superseded revisions stay out.
4. Set the folder permission to **Anyone with the link → Viewer** explicitly
   (do not rely on inherited parent permissions — bid folders often live under
   restricted parents and the inherited link silently 404s for vendors).
5. Copy the shareable URL and record it:
   ```
   node scripts/plans_registry.mjs set <jobtread_job_id> <drive_url>
   ```

The registry file (`plans_registry.json`) is git-ignored — it holds real project
URLs. Do not commit it.

### 2. Assemble the vendor list

For each scope needed (concrete, framing, HVAC, …):

- Start with JobTread's *relationship* vendors for that trade (existing accounts
  with W-9 / COI on file → fastest to onboard).
- Fill gaps with cold research: local Tampa Bay contractors, verified via
  business license, address, and public reviews.
- Dedupe against JobTread's existing vendor list before adding new ones.
- Save the combined list to `vendors_master.csv` and the *new-only* rows to
  `jobtread_vendor_import.csv` (JobTread's expected schema — see
  `scripts/push_vendors_to_jobtread.mjs` header for column names).

### 3. Push new vendors to JobTread

```
export JT_GRANT_KEY=<your JobTread grant key>
node scripts/push_vendors_to_jobtread.mjs jobtread_vendor_import.csv --verify
node scripts/push_vendors_to_jobtread.mjs jobtread_vendor_import.csv --test
node scripts/push_vendors_to_jobtread.mjs jobtread_vendor_import.csv --all
```

The script pushes bare account shells (name + type=vendor). Contact info
(email, phone, W-9, COI) is preserved in the source CSV — JobTread's Pave API
doesn't accept those fields on `createAccount`. Add them via the UI or a future
per-vendor `createContact` follow-up.

`--all` treats "already exists" errors as skips (not failures), so it's safe to
re-run against the same CSV.

### 4. Send RFPs

Fill in `templates/rfp_email.md` and `templates/rfp_sms.md` per scope. Every
outbound message includes:

- `Plans: <drive_url>` line, sourced from `plans_registry.mjs get <job_id>`.
- Scope of work only. **No budget**, no cost expectations, no allowance figures.
- Site address, submission deadline, and a single reply-to inbox.

Send rules:

- **Email**: To = your own bidding inbox (e.g. `bidding@yourdomain.com`); BCC =
  vendor emails. Never expose one vendor's address to another.
- **SMS**: One-to-one sends only. Never group-message — QUO shares the thread
  across recipients.
- **Rate limits**: Space SMS sends over ~30 sec each to stay under carrier
  flagging thresholds. Watch AgentMail bounce rate — the SES threshold is 5%;
  if you cross it, pause and clean the address list before continuing.

### 5. Track responses and follow up

- Log inbound quotes against the vendor row in `vendors_master.csv`.
- Bounced addresses → try SMS recovery ("what's your bid inbox?") before
  striking the vendor.
- If plans get revised: drop the new PDFs into `_BID_SET/` (URL stays the same),
  and send a short "plans updated on [date]" follow-up to every vendor that
  received the original RFP. Update `plans_revised_at` in the registry.

## Rules to preserve

These are constraints the agent must not violate on any project:

1. **No budget in RFP bodies.** Vendors bid to scope, not to number.
2. **BCC pattern for multi-vendor sends.** Every RFP that goes to more than one
   vendor uses BCC. TO is our own inbox.
3. **One-to-one SMS.** Never group.
4. **Plans link in every RFP.** Email and SMS. Sourced from the registry, not
   pasted per-send.
5. **Anyone-with-link view on the plans folder.** Not restricted-per-vendor.
   Vendors circulate plans internally to estimators — locking it down kills
   response rates.
