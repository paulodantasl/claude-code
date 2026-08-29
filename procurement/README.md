# Procurement Kit

Process, templates, and scripts for running vendor procurement on a construction
project. Designed to be reused across projects — none of the files here contain
project-specific data.

## What's here

| Path | Purpose |
| --- | --- |
| `RFP_WORKFLOW.md` | The end-to-end runbook: plans folder, vendor sourcing, bid requests, follow-ups. |
| `templates/rfp_email.md` | Email body template. Includes required `Plans:` line. |
| `templates/rfp_sms.md` | SMS body template. Also includes the plans link. |
| `scripts/plans_registry.mjs` | Local key/value store mapping JobTread job → shareable Drive folder URL. |
| `scripts/push_vendors_to_jobtread.mjs` | Bulk-import a vendor CSV into JobTread via the Pave API. |

## First-time setup per project

1. Confirm the JobTread↔Google Drive sync has created the project's Drive root.
2. Inside the project root, create a `_BID_SET/` subfolder and put the current-issued plans in it.
3. Right-click `_BID_SET/` → Share → *Anyone with the link* → *Viewer*. Copy the URL.
4. Record the URL against the JobTread job ID: `node scripts/plans_registry.mjs set <jobtread_job_id> <drive_url>`.

That URL is now the single source of truth for what vendors see. Every RFP references it.

## Reading the workflow

Start with [`RFP_WORKFLOW.md`](./RFP_WORKFLOW.md). It codifies the five-step
process every RFP goes through — the runbook the agent (or a human) follows for
each new project.
