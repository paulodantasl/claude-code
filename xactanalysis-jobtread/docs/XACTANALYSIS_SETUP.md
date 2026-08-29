# XactAnalysis setup — notification email to a dedicated inbox

Everything in this file is done **manually, by a person, logged into the
portal normally**. It is one-time configuration of features Verisk provides
for exactly this purpose. No automation touches XactAnalysis at any point.

## 1. Create a dedicated mailbox

Create `claims@theidealremodeling.com` (or similar) on your mail provider.
A dedicated address matters because:

- the bridge can safely treat *every* message there as a candidate assignment;
- no personal mail gets scanned;
- you can hand the credentials to the bridge without exposing anyone's inbox.

If you use Google Workspace/Gmail: enable IMAP for the account and create an
**App Password** (Google Account → Security → 2-Step Verification → App
passwords) — the bridge uses that, never your real password.

## 2. Point XactAnalysis notifications at it

In the XactAnalysis portal (your admin login):

1. **Qualifications module** — where adjusters/contractors are qualified to
   receive assignments — open your contractor record and use **Add New
   Notification** in the Adjuster/Contractor Notification section. Add the
   dedicated address for assignment notifications.
2. **Notification rules** (Personal Rules / Program Rule Notifications,
   depending on your account level) — add a rule for the **New Assignment**
   event ("notify when XactAnalysis receives a new assignment into the
   Assignment Queue or for a specific adjuster or contractor") with the
   dedicated address as recipient.
3. Keep your existing notifications to staff unchanged — this is an
   *additional* recipient, not a replacement.

Exact menu names vary a little by account type (XactAnalysis vs XactAnalysis
SP) and by carrier program. If you can't find either screen, one email to
Xactware support — "please add claims@… as a notification recipient for all
new assignments" — gets it done; this is a routine request.

## 3. Verify

Next time an assignment arrives (or ask your carrier contact to send a test
assignment), confirm the dedicated inbox receives it. Save that first real
email — drop a copy into `tests/sample_emails/` and run
`python -m src.main --once --dry-run` to confirm the parser pulls the claim
number, insured, and loss address correctly before going live.

## What NOT to do

- Do **not** give the bridge (or any tool) your XactAnalysis login.
- Do **not** auto-forward from a personal inbox that also receives portal
  password-reset emails; use the dedicated address as a direct notification
  recipient instead.
- Do **not** install browser extensions or "sync tools" that log into the
  portal on your behalf — same terms-of-use problem as scraping.
