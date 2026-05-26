# Construction Procurement Agent — v1 (Phases 0, 1a, 1b, 2)

A grounded, citation-first agent for construction procurement workflows.
This branch implements the full v1 in-scope feature set:

- **Sourcing (A)**: ingest project docs → chat with citations → draft
  trade-specific RFQs → register bids → structured extraction → side-by-side
  comparison matrices with cell-level citations and immutable snapshots.
- **Compliance/docs (B)**: derive a compliance checklist from spec language
  (or templates), bind evidence documents to requirements, and run them
  through a reviewer workflow (missing → received → under review → approved /
  rejected) with a project-wide reviewer queue and gap report.

Everything is grounded: matrices, checklists, and RFQ prose link back to the
source document page. See [Roadmap](#roadmap) for what's deferred.

## Stack

| Layer        | Choice                                          |
| ------------ | ----------------------------------------------- |
| Web          | Next.js 14 (App Router) + Tailwind + tRPC       |
| API          | Colocated tRPC routes (`/api/trpc`)             |
| Auth         | Magic link (email) — dev console transport      |
| DB           | Postgres 16 + Drizzle ORM                       |
| Search       | Postgres `tsvector` full-text (vector-ready)    |
| Jobs         | BullMQ on Redis 7                               |
| Storage      | S3-compatible (MinIO locally)                   |
| Parsing      | `pdf-parse` (page-aware) + `exceljs`            |
| LLM          | Anthropic Claude (Sonnet 4.6 by default)        |
| Languages    | TypeScript everywhere                           |

## Layout

```
apps/procurement/
├── apps/
│   ├── web/        Next.js + tRPC + UI
│   └── worker/     BullMQ worker (PDF/XLSX → chunks)
├── packages/
│   ├── db/         Drizzle schema, client, migrations
│   ├── shared/     Env loader, shared zod schemas/types
│   └── llm/        LLM provider interface + Anthropic / stub
├── fixtures/       Synthetic test fixtures + generator
├── docker-compose.yml
├── .env.example
└── README.md
```

## Quick start

```bash
cd apps/procurement
cp .env.example .env

# 1) Bring up Postgres / Redis / MinIO
pnpm infra:up

# 2) Install workspace deps
pnpm install

# 3) Generate + apply migrations, seed a dev user
pnpm db:generate
pnpm db:migrate
pnpm seed   # creates dev@example.test in "Demo GC" org with one project

# 4) Run the web app + worker together
pnpm dev
```

Then open `http://localhost:3000`, request a magic link for `dev@example.test`,
and click the link printed in the server console. You'll land in a project
workspace where you can upload PDFs/XLSX, watch them parse, and ask the agent
questions.

Set `ANTHROPIC_API_KEY` to enable the real model. Without it, a **stub
provider** runs that calls the search tool and echoes the top hits with
citations — useful for verifying the pipeline without spending tokens.

## What works in Phase 0

- Magic-link auth + session cookies (sign in, sign out, audit-logged)
- Multi-org / multi-project workspace with role-based access (`admin`,
  `procurement`, `pm_read_only`)
- Signed-URL uploads to S3-compatible storage, then signed downloads
- Stubbed virus-scan hook (`document_scans` row with `clean=true`) — wire to
  ClamAV/etc. by replacing one function
- Async parse jobs (PDF and XLSX) producing page-aware chunks indexed in
  Postgres `tsvector`
- Document viewer with PDF.js, deep-linkable to `?page=N`; parsed text shows
  side-by-side
- Chat panel per project: streams through a tool-using agent that must call
  `search_project_docs` and `get_page_text` before answering. Citations render
  as chips linking back into the viewer at the exact page.
- Audit log surface in the project UI, recording uploads, parses, chat
  messages, sign-ins, and project creation

## What's added in Phase 1a (RFQ drafting)

- **Packages tab** per project — create sourcing or compliance packages, each
  with its own RFQ drafts
- **Trade-specific templates** seeded at startup (concrete `03 30 00`,
  structural steel `05 12 00`, drywall `09 21 16`); add more in
  `packages/db/src/templates.ts`
- **Section-by-section generation**: each template section has a brief the
  agent uses to retrieve evidence and write the body. Inline citation markers
  become clickable chips back to the source PDF page.
- **Manual edits** preserved alongside generated content (an `editedAt`
  timestamp shows on-the-fly overrides)
- **Immutable versions**: "Freeze new version" snapshots the current sections;
  versions are listed with their notes and creation time
- **DOCX export**: rendered with title/heading hierarchy, citation markers
  rewritten to `(Document Name, p<n>)` inline, and a References appendix
  listing every cited source. Exports are stored in object storage and tracked
  in `rfq_exports` for audit/redownload.

## Agent design

The LLM is treated as an **orchestrator + writer** over retrieved evidence,
never as a source of facts. Two tools are exposed:

| Tool                  | Inputs                          | Outputs                                                 |
| --------------------- | ------------------------------- | ------------------------------------------------------- |
| `search_project_docs` | query, limit                    | Ranked hits with `documentId`, `page`, `chunkId`, snippet |
| `get_page_text`       | documentId, page                | Full text of the page (all chunks concatenated)         |

The system prompt requires inline citation markers like `[doc:<uuid> p<n>]`,
which the UI rewrites into clickable chips. Hits returned by
`search_project_docs` are also surfaced as a chip row beneath the message so
the user can verify even when the model forgets a marker. Tool inputs are
validated server-side before any DB query runs.

Provider selection lives in `packages/llm/src/index.ts`:

```ts
selectProvider({ apiKey, model }) // returns AnthropicProvider or StubProvider
```

Adding OpenAI/etc. is one new file implementing the `LlmProvider` interface.

## Data model

See `packages/db/src/schema.ts`. Phase 0 ships:

- `organizations`, `users`, `memberships` (RBAC)
- `magic_link_tokens`, `sessions`
- `projects`, `packages` (sourcing / compliance), `vendors`
- `documents`, `document_scans`, `document_chunks` (with FTS gin index)
- `chat_threads`, `chat_messages` (citations + tool trace JSON)
- `audit_events`

Phase 1 entities (`requirement_items`, `fulfillments`, `bids`,
`comparison_runs`, `rfq_drafts`) will add to this schema without breaking
existing tables.

## Security notes

- All uploads/downloads use signed URLs (15 min upload TTL, 1 hr download TTL)
- Project-scoped tRPC procedure (`projectProcedure`) enforces org membership
  on every read/write to documents, chunks, audit, and chat
- Magic-link tokens are stored as SHA-256 hashes with single-use enforcement
- Session cookies are `HttpOnly`, `SameSite=Lax`, and rotated on each sign-in
- LLM tool inputs are validated through Zod schemas in `packages/shared/src/types.ts`
- Tenant isolation enforced at the SQL layer — every chat/search query joins on
  `projectId` before returning chunks

## What's added in Phase 1b (bids + comparison)

- **Vendor directory** scoped to the organization (basic create/list)
- **Bid registration**: link a parsed bid document to a vendor for a package
  (one bid per document, enforced by unique index)
- **LLM-driven extraction**: forced tool-use schema makes the model emit a
  structured list of line items with category (`base` / `alternate` /
  `allowance` / `exclusion`), qty/unit/unitPrice/extended, lead time, and
  per-row source page + snippet. Stub extractor parses tab-separated XLSX text
  heuristically for offline dev.
- **Comparison matrix**: pick 2+ extracted bids, name the run, get an
  immutable `comparison_runs` snapshot. Rows are normalized line items grouped
  by description; cells show each vendor's extended price + unit price + a
  citation chip linking to the source page in the bid PDF/XLSX viewer.
- **Auto-flagging** (pure TS, predictable): missing bids on base lines,
  exclusions called out by any vendor, and outlier cells (>1.5× or <0.5×
  median of vendors that quoted).
- **Totals row**: base bid total, net of alternates, lead time per vendor.

## What's added in Phase 2 (compliance pack)

- **Requirement templates** seeded at startup: a general vendor-onboarding
  checklist (COI, W-9, lien waiver, safety plan) and a concrete-submittals
  checklist. Add more in `packages/db/src/templates.ts`.
- **Derive from spec (AI)**: retrieves spec passages and uses a forced
  tool-use schema to propose requirements — label, artifact kind, severity
  (required/recommended/optional), and a source clause + page + snippet for
  provenance. Stub deriver scans for submittal/cert/warranty keywords offline.
- **Evidence binding**: attach a parsed document (and page) to a requirement;
  bindings are append-only `fulfillments` rows, newest = current.
- **Reviewer workflow**: per-requirement status transitions
  (missing → received → under review → approved / rejected) with reviewer
  notes, plus a **project-wide reviewer queue** tab and a **gap report**
  (counts by status, count of still-open required items).
- Compliance checklist appears on every package; requirement source clauses
  and bound evidence render as citation chips into the document viewer.

## Roadmap (deferred)

- **Eval harness**: golden-key fixtures in `fixtures/expected/`,
  precision/recall on compliance gaps, cell accuracy on comparison matrices
- **Exports**: comparison matrix XLSX/PDF; compliance pack PDF with a
  citation-backed appendix
- **Polish**: comparison-run re-run with fresh bids; per-vendor requirement
  scoping in the UI; vendor portal upload links; ERP/PO issuance (out of v1
  scope)

## Development tips

- `pnpm db:studio` opens Drizzle Studio
- `pnpm infra:reset` wipes Postgres + MinIO data and restarts everything
- The stub LLM provider runs by default if `ANTHROPIC_API_KEY` is blank —
  great for offline CI
- Worker logs queue events to stdout; use `BULL_BOARD` later if you want a UI
- PDF/XLSX are size-capped at 200 MB in `requestUpload` — adjust if you need
  bigger drawings
