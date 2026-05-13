# Construction Procurement Agent — Phase 0

A grounded, citation-first agent for construction procurement workflows
(RFQs, bid comparison, compliance packs). This branch ships **Phase 0 only**:
a working monorepo with project workspaces, document uploads, async PDF/XLSX
parsing, and a chat interface that answers questions with clickable citations
into the original document pages.

The rest of the v1 plan (RFQ drafting, bid normalization, compliance
templates) plugs into the same schema, queue, and tool interface — see
[Roadmap](#roadmap).

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

## Roadmap (next slices)

- **Phase 1a — RFQ drafting**: template library per trade, agent fills sections
  from retrieved spec clauses, versioned drafts, DOCX/PDF export
- **Phase 1b — Bid intake & comparison**: normalize bids to a line-item schema
  (allowances, alternates, exclusions, lead times), generate immutable
  `comparison_runs` snapshots with cell-level citations
- **Phase 2 — Compliance pack**: checklist templates per package type, fulfill
  with evidence spans, reviewer workflow (missing → received → approved),
  generate compliance pack PDF with citation appendix
- **Phase 3 — Eval harness**: golden-key fixtures in `fixtures/expected/`,
  precision/recall on compliance gaps, cell accuracy on comparison matrices

## Development tips

- `pnpm db:studio` opens Drizzle Studio
- `pnpm infra:reset` wipes Postgres + MinIO data and restarts everything
- The stub LLM provider runs by default if `ANTHROPIC_API_KEY` is blank —
  great for offline CI
- Worker logs queue events to stdout; use `BULL_BOARD` later if you want a UI
- PDF/XLSX are size-capped at 200 MB in `requestUpload` — adjust if you need
  bigger drawings
