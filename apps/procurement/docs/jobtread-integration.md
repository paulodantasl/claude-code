# JobTread integration — design sketch

> **Status: exploration / design only — no code yet.** Verified what's public
> on JobTread's site, marketing pages, and search results. The exact GraphQL
> schema sits behind their API Developer Certification page (`HTTP 403` for
> anonymous fetchers), so several field names below are best-effort and
> labeled **(verify)**. We should confirm these against a real account's
> introspection or their cert docs before writing the client.

## What's confirmed about the API

- **Endpoint**: `POST https://api.jobtread.com/pave`
- **Content type**: `application/json`
- **Auth**: a personal **grantKey** (prefix `grant_`) created at
  `https://app.jobtread.com/grants`. Sent under `query.$.grantKey` in every
  request — there is no separate Authorization header.
- **Query language**: their own thing called **Pave**, GraphQL-like but with
  a `$` envelope on each node carrying control fields:
  - `$.grantKey` — required
  - `$.notify` — suppress notification emails
  - `$.timeZone` — scope timestamp returns
  - `$.viaUserId` — act on behalf of a user
- **Entities exposed (publicly named)**: `customer`, `vendor`, `job`,
  `location`, `task`, `document`, `customField`, plus webhook subscriptions.
- **Webhooks** are supported (lifecycle managed via the same API).
- **Pagination + filtering**: `where` and `sortBy` arguments on collection
  fields; the cert curriculum specifically lists "Pagination & Aggregation".
- **Rate limits & batch limits**: not publicly stated. Their cert page lists
  a "Platform Stability & Limits" module — assume sane limits exist; we'll
  back off on 429s defensively.

Sources at the bottom of this doc.

## Integration shape (recommended)

**Phase A — one-way pull (start here, low risk)**

1. User adds a JobTread `grantKey` in our app settings.
2. We expose a "Sync from JobTread" action per org or per project:
   - Pull the list of **jobs** → users pick one → we create / link a
     `Project` row in our app, storing the JobTread job id on it.
   - Pull **vendors** attached to that job's org → upsert into our
     `vendors` table; key on JobTread vendor id (kept in a new column).
3. Optionally pull cost items (the SOV / estimate line items) as a starter
   set of `procurement_requests` — one per line that needs a sub or vendor
   quote. **(verify the cost-item field names)**.

**Phase B — round-trip (later, optional)**

1. When a `procurement_request` reaches `recommended`, push an artifact back
   to JobTread:
   - Create a **document** on the linked JobTread job (the RFQ DOCX export
     and / or the comparison-run PDF) — **verify document upload API exists,
     or attach as URL**.
   - Create a **task** on the job: "Award contract to {vendor} — base bid
     {amount}". Assign it.
2. Subscribe to JobTread webhooks for vendor and job changes so our copy
   stays fresh without polling.

**What we deliberately won't try in v1**: creating subcontracts / POs in
JobTread, syncing financials. Those are higher-blast-radius writes and the
field shapes need real validation.

## Entity mapping (best-effort)

| Our entity              | JobTread entity        | Direction | Notes |
| ----------------------- | ---------------------- | --------- | ----- |
| `projects`              | `Job`                  | pull      | Add `external_id`, `external_source='jobtread'` cols. |
| `vendors`               | `Vendor`               | pull      | Same — store JobTread vendor id. |
| `procurement_requests`  | `CostItem` (line item) | pull (opt) | One request seeded per line item the user picks. **(verify)** |
| `rfq_exports` (DOCX)    | `Document` on Job      | push      | Phase B. **(verify file-upload mutation)** |
| `comparison_runs`       | `Task` + `Document` on Job | push  | Phase B. |

Custom fields would also let us round-trip our request id onto the JobTread
side — useful for webhook dedup.

## Code shape we'd add

```
packages/jobtread/
├── package.json
└── src/
    ├── client.ts         # POST /pave wrapper, grantKey injection, retries
    ├── queries.ts        # Pave query builders for jobs, vendors, costItems
    ├── types.ts          # Manually-typed minimal interfaces
    └── index.ts

apps/web/src/server/
├── routers/jobtread.ts   # tRPC: listJobs, importJob, importVendors, syncBack
└── jobtread/             # sync logic, upserts keyed on external_id

apps/procurement/packages/db/src/schema.ts
└── add: external_id (varchar), external_source (varchar) on projects + vendors
```

## Open questions to verify before writing the client

1. **Cost-item shape**: exact field names — `name`, `quantity`, `unit`,
   `unitCost`, `totalCost`, and any nested specs / notes? Are they nested
   under `Job.costItems` or fetched via a separate `costItem` collection?
2. **Document upload**: does the API accept file bytes (multipart, base64
   field) or only metadata + an externally-hosted URL? If metadata-only, we
   can host our exports on our MinIO and pass a presigned URL.
3. **Vendor scope**: are vendors per-org or per-job? Does the customer/vendor
   API differentiate at all (some platforms call all parties "contacts")?
4. **Webhook payload**: which events are subscribable, and what fields are
   on the payload? Need to know to design webhook handlers idempotently.
5. **Rate limits**: published or unstated? Plan for 5 req/s with exponential
   backoff until we confirm.
6. **Pagination**: cursor or offset? Page size cap?

We can answer 1-2 of these by signing into a sandbox JobTread tenant and
running an introspection-style query, or by enrolling in the API Developer
Certification (free per their docs).

## Cost & complexity to deliver

- **Phase A** (one-way pull, jobs + vendors): ~1-2 days of work once
  questions 1-3 are answered. Builds on our existing schema with two new
  columns and one tRPC router.
- **Phase B** (round-trip + webhooks): another ~3-5 days, dominated by
  webhook handler idempotency and document upload semantics.

## Sources

- [JobTread Open API page](https://www.jobtread.com/integrations/open-api) — 403 to anonymous fetch; describes the Pave endpoint and grantKey flow.
- [JobTread API Developer Certification](https://www.jobtread.com/resources/training/certifications/api-developer) — outlines the curriculum (Pave querying, relationships, pagination, webhooks, limits).
- [JobTread Integrations](https://www.jobtread.com/integrations) — lists official integration partners; helpful for understanding their integration model.
- [JobTread Partners — Integration Partner](https://www.jobtread.com/partners/integration-partner) — partnership and developer onboarding.
- [JobTread on GitHub](https://github.com/jobtread) — only two public repos (status page + a JS project); no public SDK.
- [Skill: JobTread via Pave Query API (lobehub)](https://lobehub.com/skills/openclaw-skills-jobtread-api) — third-party summary of Pave usage and the query.$ envelope.
- [JobTread connector on Make.com](https://apps.make.com/job-tread-nwht6n) — lists supported actions/triggers, useful as evidence of which entities are reachable.
