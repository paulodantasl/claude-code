# Safe ways to get XactAnalysis claims into JobTread

This document is the research behind the recommendation in the main README.
The constraint driving everything: **the last attempt used automated portal
access and Verisk blocked the account.** Verisk (Xactware) explicitly forbids
bots, scrapers, and scripted logins to XactAnalysis, and their detection is
aggressive because the network carries carrier claim data. A second offense
risks permanent removal from the assignment network — the one outcome worse
than having no integration.

So every option below shares one property: **no software ever logs into or
requests pages from xactanalysis.com.**

---

## Option 1 — Assignment notification emails → JobTread API (recommended)

**How it works.** XactAnalysis automatically sends an email notification to the
assigned contractor whenever a new assignment arrives — this is core product
behavior, not a workaround. Notification recipients and events are configured
in the portal (Qualifications → Adjuster/Contractor Notifications, and
Personal/Program Rule Notifications support a *New Assignment* event). You
point those notifications at a mailbox you own, and this repo's service reads
that mailbox over IMAP and creates the lead in JobTread via their public Open
API (the Pave query API at `https://api.jobtread.com/pave`, authenticated with
a grant key you generate in JobTread settings).

**Why it's safe.**
- Verisk *pushes* the email to you; nothing automated ever contacts their
  systems. There is nothing to detect and nothing to block.
- JobTread's Open API is public, documented, and intended exactly for this
  (their docs: "Utilizing JobTread's Open API", and they run an integration
  partner program).

**Limitations.**
- The email contains the assignment summary (claim number, insured, loss
  address, peril, adjuster, etc.), not the full estimate/sketch data. For a
  *new-lead* trigger that's all you need; estimates continue to live in
  Xactimate/XactAnalysis as they do today.
- Notification email templates vary slightly by carrier/program, so the parser
  is written defensively and always preserves the full email body in the
  JobTread job description as a fallback.

**Cost:** $0 beyond wherever you run the script (a $5 VPS, an office PC, or a
scheduled GitHub Action on a private repo).

---

## Option 2 — Same architecture, no code (Zapier)

JobTread has a first-class Zapier app, and Zapier offers "Email Parser by
Zapier" / "Email by Zapier" triggers. Auto-forward the XactAnalysis
notification mailbox to a Zapier parser address, teach the parser the fields
once by highlighting them in a sample email, and map them into JobTread's
"Create Customer / Create Job" actions.

- Pros: no server, no code, visible run history, ~1 hour to set up.
- Cons: monthly Zapier cost at real volume; the point-and-click parser is less
  tolerant of template variations than the regex parser in this repo; per-task
  limits.

Setup walkthrough: [`ZAPIER_NOCODE_OPTION.md`](ZAPIER_NOCODE_OPTION.md).

---

## Option 3 — Verisk's official third-party export (EDI / XML)

XactAnalysis has a sanctioned integration channel: **Administration → Company
Setup and Exports**, where assignment data can be exported (manually or
automatically for every new assignment) to an integrated third-party system as
XML/EDI. This is how JobNimbus, DASH, ClickClaims, Albi, ClientRunner,
Restoration Manager, PSA, Xcelerate and others receive assignments.

The catch: **JobTread is not currently in Verisk's integration ecosystem**, so
there is no "Export to JobTread" toggle today. Your paths here:

1. **Ask your Xactware account rep** what it takes to enable exports to a
   custom endpoint or to add a partner — Verisk runs a vendor-alliance/partner
   program. This is a business conversation, not a technical one.
2. **Ask JobTread** (support or their integration-partner program) whether an
   XactAnalysis integration is on their roadmap — customer requests are how
   these get prioritized.
3. **Bridge through an already-integrated product** (e.g., receive into
   ClickClaims/JobNimbus via the official export, then Zapier/API to JobTread).
   Works, but you're paying for and maintaining an extra system — only worth it
   if you need full estimate data flowing, not just leads.

This is the "deepest" integration (structured XML with full assignment data),
but it has lead time and likely fees. **Recommended play: start Option 1 today,
open the Option 3 conversation with your rep in parallel.**

---

## Option 4 — Portal scraping / automated login: never again

For completeness, what happened last time and why it can't be retried:

- Automated logins (Selenium, headless Chrome, scripted sessions) violate the
  XactAnalysis terms of use and trip Verisk's bot detection.
- Carriers hold Verisk to strict data-security obligations, so enforcement is
  not negotiable; blocks can escalate to permanent network removal, which
  would end carrier assignment flow to the business.
- Even "just checking for new claims every few minutes" is exactly the traffic
  pattern their detection looks for.

If a future need ever requires portal data beyond what the email/export
channels give you, the answer is a conversation with Verisk (Option 3), not a
better-hidden bot.

---

## Sources

- Verisk — XactAnalysis for Service Providers: <https://www.verisk.com/insurance/products/xactanalysis-sp/>
- Verisk partner ecosystem / vendor alliances: <https://www.verisk.com/company/vendor-alliances/>
- XactAnalysis help — Integrations: <https://xactanalysis.helpdocs.io/l/enUS/article/tsfcg2l879-xact-analysis-integrations>
- XactAnalysis SP help — Company Setup & Exports: <https://xactanalysis-sp.helpdocs.io/l/enAU/article/53c1qcxaqi-company-setup-exports-en-au>
- XactAnalysis help — Program Rule Notifications (New Assignment event): <https://xactanalysis.helpdocs.io/l/enUS/article/tp5bm5g4m1-program-rule-notifications>
- XactAnalysis help — Qualifications (contractor notification setup): <https://xactanalysis.helpdocs.io/l/enUS/article/9l8n4ltyxs-qualifications>
- Xactware press — project-management integrations for contractors: <https://www.verisk.com/company/newsroom/xactware-offers-new-project-management-integration-for-contractors/>
- JobNimbus × Xactware integration (example of the official export channel): <https://support.jobnimbus.com/how-do-i-enable-the-jobnimbus-integration-with-xactimate>
- JobTread — Open API: <https://www.jobtread.com/integrations/open-api>
- JobTread — Utilizing JobTread's Open API: <https://app.jobtread.com/help/utilizing-jobtreads-open-api>
- JobTread — Zapier integrations: <https://www.jobtread.com/integrations/zapier>
- JobTread — integration partner program: <https://www.jobtread.com/partners/integration-partner>
