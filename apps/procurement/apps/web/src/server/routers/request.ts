import { z } from "zod";
import { and, asc, desc, eq } from "drizzle-orm";
import { TRPCError } from "@trpc/server";
import {
  bids as bidsTable,
  comparisonRuns,
  documents,
  packages as packagesTable,
  procurementRequestMessages,
  procurementRequests,
  rfqDrafts,
  rfqTemplates,
  vendors,
  type NeedSpec,
  type RequestArtifact,
} from "@procurement/db";
import {
  selectOrchestrator,
  type ArtifactRef,
  type OrchestratorState,
  type OrchestratorStatus,
  type OrchestratorTools,
  type ToolAction,
} from "@procurement/llm";
import { db } from "@/lib/db";
import { env } from "@/lib/env";
import { recordAudit } from "@/lib/audit";
import { searchProjectDocs } from "../search";
import { generateRfqSection } from "../rfq-generator";
import { buildComparisonMatrix } from "../comparison-builder";
import { router, projectProcedure, writeProjectProcedure } from "../trpc";

const orchestrator = selectOrchestrator({
  apiKey: env.ANTHROPIC_API_KEY,
  model: env.ANTHROPIC_MODEL,
});

const EMPTY_NEED: NeedSpec = {
  item: null,
  quantity: null,
  unit: null,
  deadline: null,
  jurisdiction: null,
  trade: null,
  specs: [],
  notes: null,
};

async function loadRequest(projectId: string, requestId: string) {
  const row = (
    await db
      .select()
      .from(procurementRequests)
      .where(
        and(
          eq(procurementRequests.id, requestId),
          eq(procurementRequests.projectId, projectId),
        ),
      )
      .limit(1)
  )[0];
  if (!row) throw new TRPCError({ code: "NOT_FOUND" });
  return row;
}

export const requestRouter = router({
  list: projectProcedure.query(async ({ ctx }) => {
    return db
      .select()
      .from(procurementRequests)
      .where(eq(procurementRequests.projectId, ctx.project.id))
      .orderBy(desc(procurementRequests.createdAt));
  }),

  create: writeProjectProcedure
    .input(
      z.object({
        projectId: z.string().uuid(),
        title: z.string().min(1).max(200),
        initialMessage: z.string().min(1).max(4000),
      }),
    )
    .mutation(async ({ ctx, input }) => {
      const [req] = await db
        .insert(procurementRequests)
        .values({
          projectId: ctx.project.id,
          title: input.title,
          status: "intake",
          need: { ...EMPTY_NEED },
          createdBy: ctx.session.userId,
        })
        .returning();
      if (!req) throw new TRPCError({ code: "INTERNAL_SERVER_ERROR" });
      await db.insert(procurementRequestMessages).values({
        requestId: req.id,
        role: "user",
        content: input.initialMessage,
      });
      await recordAudit({
        organizationId: ctx.project.organizationId,
        projectId: ctx.project.id,
        userId: ctx.session.userId,
        action: "procurement_request.create",
        targetType: "procurement_request",
        targetId: req.id,
        metadata: { title: input.title },
      });
      // Run the first orchestrator turn synchronously so the user sees something.
      await runTurn({
        projectId: ctx.project.id,
        organizationId: ctx.project.organizationId,
        userId: ctx.session.userId,
        request: req,
        userMessage: input.initialMessage,
      });
      return req;
    }),

  get: projectProcedure
    .input(z.object({ projectId: z.string().uuid(), requestId: z.string().uuid() }))
    .query(async ({ ctx, input }) => {
      const req = await loadRequest(ctx.project.id, input.requestId);
      const messages = await db
        .select()
        .from(procurementRequestMessages)
        .where(eq(procurementRequestMessages.requestId, req.id))
        .orderBy(asc(procurementRequestMessages.createdAt));
      return { request: req, messages };
    }),

  sendMessage: writeProjectProcedure
    .input(
      z.object({
        projectId: z.string().uuid(),
        requestId: z.string().uuid(),
        message: z.string().min(1).max(4000),
      }),
    )
    .mutation(async ({ ctx, input }) => {
      const req = await loadRequest(ctx.project.id, input.requestId);
      await db.insert(procurementRequestMessages).values({
        requestId: req.id,
        role: "user",
        content: input.message,
      });
      return runTurn({
        projectId: ctx.project.id,
        organizationId: ctx.project.organizationId,
        userId: ctx.session.userId,
        request: req,
        userMessage: input.message,
      });
    }),

  cancel: writeProjectProcedure
    .input(z.object({ projectId: z.string().uuid(), requestId: z.string().uuid() }))
    .mutation(async ({ ctx, input }) => {
      const req = await loadRequest(ctx.project.id, input.requestId);
      await db
        .update(procurementRequests)
        .set({ status: "cancelled", updatedAt: new Date() })
        .where(eq(procurementRequests.id, req.id));
      await recordAudit({
        organizationId: ctx.project.organizationId,
        projectId: ctx.project.id,
        userId: ctx.session.userId,
        action: "procurement_request.cancel",
        targetType: "procurement_request",
        targetId: req.id,
      });
      return { ok: true };
    }),
});

// ============================================================================
// Tool bindings — translate orchestrator tool calls into real DB / function
// invocations. State updates from the orchestrator are persisted at the end
// of the turn.
// ============================================================================

async function runTurn(opts: {
  projectId: string;
  organizationId: string;
  userId: string;
  request: typeof procurementRequests.$inferSelect;
  userMessage: string;
}) {
  const { projectId, organizationId, userId, request, userMessage } = opts;
  // Mutable working copy of the request fields the agent can update.
  let workingNeed: NeedSpec = request.need;
  let workingPackageId = request.packageId;
  let workingRfqDraftId = request.rfqDraftId;

  const tools: OrchestratorTools = {
    extract_need: async ({ text }) => heuristicExtract(text, workingNeed),

    update_need: async ({ fields }) => {
      workingNeed = {
        ...workingNeed,
        ...Object.fromEntries(
          Object.entries(fields).filter(([, v]) => v !== undefined),
        ),
      };
      return workingNeed;
    },

    search_project_docs: async ({ query, limit }) => ({
      hits: await searchProjectDocs(projectId, query, limit ?? 8),
    }),

    list_rfq_templates: async ({ trade }) => {
      const rows = await db.select().from(rfqTemplates);
      const filtered = trade ? rows.filter((r) => r.trade === trade) : rows;
      return filtered.map((r) => ({
        id: r.id,
        name: r.name,
        trade: r.trade,
        division: r.division,
      }));
    },

    create_package_and_rfq_draft: async ({ title, templateId }) => {
      const tpl = (
        await db.select().from(rfqTemplates).where(eq(rfqTemplates.id, templateId)).limit(1)
      )[0];
      if (!tpl) throw new Error("Template not found");

      const [pkg] = await db
        .insert(packagesTable)
        .values({
          projectId,
          kind: "sourcing",
          name: title,
        })
        .returning();
      if (!pkg) throw new Error("Failed to create package");
      const emptySections = tpl.sections.map((s) => ({
        id: s.id,
        title: s.title,
        body: "",
        citations: [],
        generatedAt: null,
        editedAt: null,
      }));
      const [draft] = await db
        .insert(rfqDrafts)
        .values({
          projectId,
          packageId: pkg.id,
          templateId: tpl.id,
          title,
          currentSections: emptySections,
          createdBy: userId,
        })
        .returning();
      if (!draft) throw new Error("Failed to create RFQ draft");
      workingPackageId = pkg.id;
      workingRfqDraftId = draft.id;
      await recordAudit({
        organizationId,
        projectId,
        userId,
        action: "procurement_request.package_created",
        targetType: "rfq_draft",
        targetId: draft.id,
        metadata: { requestId: request.id, templateId: tpl.id },
      });
      return {
        packageId: pkg.id,
        rfqDraftId: draft.id,
        sections: tpl.sections.map((s) => ({ id: s.id, title: s.title })),
      };
    },

    generate_rfq_section: async ({ sectionId }) => {
      if (!workingRfqDraftId) throw new Error("No RFQ draft yet");
      const draft = (
        await db.select().from(rfqDrafts).where(eq(rfqDrafts.id, workingRfqDraftId)).limit(1)
      )[0];
      if (!draft) throw new Error("RFQ draft missing");
      const tpl = (
        await db.select().from(rfqTemplates).where(eq(rfqTemplates.id, draft.templateId)).limit(1)
      )[0];
      const spec = tpl?.sections.find((s) => s.id === sectionId);
      if (!spec) throw new Error(`Unknown section ${sectionId}`);
      const filled = await generateRfqSection({
        projectId,
        userId,
        section: spec,
        rfqTitle: draft.title,
        projectName: workingNeed.item ?? draft.title,
      });
      const merged = draft.currentSections.map((s) => (s.id === filled.id ? filled : s));
      if (!merged.some((s) => s.id === filled.id)) merged.push(filled);
      await db
        .update(rfqDrafts)
        .set({ currentSections: merged, updatedAt: new Date() })
        .where(eq(rfqDrafts.id, draft.id));
      return {
        sectionId,
        citationCount: filled.citations.length,
        bodyPreview: filled.body.slice(0, 200),
      };
    },

    list_vendors: async ({ trade }) => {
      const rows = await db
        .select()
        .from(vendors)
        .where(eq(vendors.organizationId, organizationId));
      const filtered = trade ? rows.filter((v) => v.trades.includes(trade)) : rows;
      return filtered.map((v) => ({
        id: v.id,
        name: v.name,
        trades: v.trades,
        contactEmail: v.contactEmail,
      }));
    },

    list_bids: async () => {
      if (!workingPackageId) return [];
      const rows = await db
        .select({ bid: bidsTable, vendor: vendors, doc: documents })
        .from(bidsTable)
        .innerJoin(vendors, eq(vendors.id, bidsTable.vendorId))
        .innerJoin(documents, eq(documents.id, bidsTable.documentId))
        .where(eq(bidsTable.packageId, workingPackageId));
      return rows.map((r) => ({
        bidId: r.bid.id,
        vendorName: r.vendor.name,
        documentTitle: r.doc.title,
        extracted: r.bid.extractedAt != null,
        baseTotalCents: r.bid.baseTotal,
        leadTimeWeeks: r.bid.leadTimeWeeks,
      }));
    },

    create_comparison: async ({ title }) => {
      if (!workingPackageId) throw new Error("No package yet");
      const rows = await db
        .select({ bid: bidsTable, vendor: vendors })
        .from(bidsTable)
        .innerJoin(vendors, eq(vendors.id, bidsTable.vendorId))
        .where(eq(bidsTable.packageId, workingPackageId));
      const extracted = rows.filter((r) => r.bid.extractedAt && r.bid.lineItems.length > 0);
      if (extracted.length < 2) {
        throw new Error(`Need at least 2 extracted bids (have ${extracted.length})`);
      }
      const matrix = buildComparisonMatrix({
        bids: extracted.map((r) => ({ ...r.bid, vendor: r.vendor })),
      });
      // Score: lowest base total wins, lead time as tiebreaker.
      const ranking = matrix.vendors
        .map((v) => ({
          vendorId: v.id,
          name: v.name,
          baseCents: matrix.totals[v.id]?.baseCents ?? null,
          leadTime: matrix.totals[v.id]?.leadTimeWeeks ?? null,
        }))
        .filter((r) => r.baseCents != null)
        .sort((a, b) => {
          if (a.baseCents !== b.baseCents) return (a.baseCents ?? 0) - (b.baseCents ?? 0);
          return (a.leadTime ?? Number.MAX_SAFE_INTEGER) - (b.leadTime ?? Number.MAX_SAFE_INTEGER);
        });
      const winner = ranking[0];
      const recommendationReason = winner
        ? buildRecommendationReason(winner, ranking, matrix)
        : "No vendor had a usable base total to compare.";
      const [run] = await db
        .insert(comparisonRuns)
        .values({
          projectId,
          packageId: workingPackageId,
          title,
          bidIds: extracted.map((r) => r.bid.id),
          matrix,
          assumptions: [
            `${extracted.length} vendors compared on ${matrix.rows.length} normalized lines.`,
            "Auto-generated as part of procurement request orchestration.",
          ],
          createdBy: userId,
        })
        .returning();
      if (!run) throw new Error("Failed to create comparison run");
      await recordAudit({
        organizationId,
        projectId,
        userId,
        action: "procurement_request.comparison_created",
        targetType: "comparison_run",
        targetId: run.id,
        metadata: { requestId: request.id, recommendedVendor: winner?.name ?? null },
      });
      return {
        comparisonRunId: run.id,
        rowCount: matrix.rows.length,
        flagCount: matrix.flags.length,
        recommendedVendorId: winner?.vendorId ?? null,
        recommendedVendorName: winner?.name ?? null,
        recommendationReason,
      };
    },

    set_status: async ({ status }) => {
      await db
        .update(procurementRequests)
        .set({ status: status as OrchestratorStatus, updatedAt: new Date() })
        .where(eq(procurementRequests.id, request.id));
    },

    set_recommendation: async ({ text }) => {
      await db
        .update(procurementRequests)
        .set({ recommendation: text, updatedAt: new Date() })
        .where(eq(procurementRequests.id, request.id));
    },
  };

  const history = await db
    .select()
    .from(procurementRequestMessages)
    .where(eq(procurementRequestMessages.requestId, request.id))
    .orderBy(asc(procurementRequestMessages.createdAt));

  const state: OrchestratorState = {
    need: request.need,
    status: request.status,
    packageId: request.packageId,
    rfqDraftId: request.rfqDraftId,
    comparisonRunId: request.comparisonRunId,
    recommendation: request.recommendation,
  };

  const result = await orchestrator.runTurn({
    state,
    history: history
      .slice(0, -1) // drop the just-inserted user message — orchestrator gets it as userMessage
      .map((m) => ({
        role: m.role === "user" ? ("user" as const) : ("assistant" as const),
        content: m.content,
      })),
    userMessage,
    tools,
  });

  // Persist state updates (merge agent's view + tools' direct writes).
  const updates: Partial<typeof procurementRequests.$inferInsert> = { updatedAt: new Date() };
  if (result.stateUpdates.need) updates.need = result.stateUpdates.need;
  else if (workingNeed !== request.need) updates.need = workingNeed;
  if (workingPackageId !== request.packageId) updates.packageId = workingPackageId;
  if (workingRfqDraftId !== request.rfqDraftId) updates.rfqDraftId = workingRfqDraftId;
  if (result.stateUpdates.comparisonRunId !== undefined)
    updates.comparisonRunId = result.stateUpdates.comparisonRunId;
  if (result.stateUpdates.status) updates.status = result.stateUpdates.status;
  if (result.stateUpdates.recommendation !== undefined)
    updates.recommendation = result.stateUpdates.recommendation;
  await db
    .update(procurementRequests)
    .set(updates)
    .where(eq(procurementRequests.id, request.id));

  const artifacts: RequestArtifact[] = result.artifacts.map((a: ArtifactRef) => ({
    kind: a.kind,
    id: a.id,
    label: a.label,
  }));

  const [agentMsg] = await db
    .insert(procurementRequestMessages)
    .values({
      requestId: request.id,
      role: "agent",
      content: result.reply,
      artifacts,
      actions: result.actions as ToolAction[],
    })
    .returning();

  await recordAudit({
    organizationId,
    projectId,
    userId,
    action: "procurement_request.turn",
    targetType: "procurement_request",
    targetId: request.id,
    metadata: {
      toolCallCount: result.actions.length,
      artifactCount: artifacts.length,
      status: updates.status ?? state.status,
    },
  });

  return { reply: result.reply, artifacts, actions: result.actions, agentMessageId: agentMsg?.id };
}

// ----------------------------------------------------------------------------
// Heuristic need extraction (offline / fallback). Pulls quantity/unit/trade/
// item out of natural language using regex; lets the LLM do this more
// robustly when ANTHROPIC_API_KEY is set, but covers the stub path.
// ----------------------------------------------------------------------------
function heuristicExtract(text: string, current: NeedSpec): Partial<NeedSpec> {
  const fields: Partial<NeedSpec> = {};
  const lower = text.toLowerCase();

  // Quantity + unit
  if (current.quantity == null) {
    const qty = text.match(
      /(\d[\d,]*(?:\.\d+)?)\s*(cubic\s+yards?|cy|cu\s*yd|tons?|sf|sq\s*ft|square\s+feet|lf|linear\s+feet|each|ea|pieces?|pcs|ls|lump\s*sum|gallons?|gal)/i,
    );
    if (qty) {
      fields.quantity = Number(qty[1]!.replace(/,/g, ""));
      fields.unit = canonicalUnit(qty[2]!);
    }
  }

  // Trade
  if (!current.trade) {
    if (/concrete|footing|slab|cast.in.place|cip/i.test(lower)) fields.trade = "concrete";
    else if (/structural steel|steel framing|beams|columns|aisc/i.test(lower))
      fields.trade = "structural_steel";
    else if (/drywall|gypsum|sheetrock|partition/i.test(lower)) fields.trade = "drywall";
  }

  // Item: strip "I need / we need / please procure" preamble, then keep up to
  // the first natural stop (comma, ". ", " for ", " by ", " in ", " delivered").
  if (!current.item) {
    const cleaned = text
      .replace(/\s+/g, " ")
      .replace(
        /^\s*(i\s+(?:need|want|require)|we\s+(?:need|require)|please\s+procure|procure|need|want|get me|order)\s+/i,
        "",
      )
      .trim();
    const stop = cleaned.search(/,|\.\s| for | by | in | delivered? /i);
    const item = (stop > 0 ? cleaned.slice(0, stop) : cleaned).trim();
    fields.item = item.length > 100 ? item.slice(0, 97) + "…" : item;
  }

  // Deadline phrasings
  if (!current.deadline) {
    const inWeeks = text.match(/in\s+(\d+)\s+weeks?/i);
    const inDays = text.match(/in\s+(\d+)\s+days?/i);
    const asap = /\basap\b/i.test(lower);
    if (asap) fields.deadline = "ASAP";
    else if (inWeeks) fields.deadline = `+${inWeeks[1]}w`;
    else if (inDays) fields.deadline = `+${inDays[1]}d`;
  }

  // Specs — look for common phrasings ("4000 psi", "ASTM C150", "Type I/II")
  const specs: string[] = [];
  const psi = text.match(/(\d{3,5})\s*psi/i);
  if (psi) specs.push(`${psi[1]} psi`);
  const astm = text.match(/ASTM\s+[A-Z]\d+/g);
  if (astm) specs.push(...astm);
  if (specs.length > 0) fields.specs = Array.from(new Set([...(current.specs ?? []), ...specs]));

  return fields;
}

function canonicalUnit(raw: string): string {
  const u = raw.toLowerCase();
  if (/cubic|cy|cu\s*yd/.test(u)) return "CY";
  if (/ton/.test(u)) return "tons";
  if (/sf|sq\s*ft|square/.test(u)) return "SF";
  if (/lf|linear/.test(u)) return "LF";
  if (/each|ea|piece|pcs/.test(u)) return "EA";
  if (/ls|lump/.test(u)) return "LS";
  if (/gallon|gal/.test(u)) return "GAL";
  return raw;
}

function buildRecommendationReason(
  winner: { name: string; baseCents: number | null; leadTime: number | null },
  ranking: Array<{ name: string; baseCents: number | null; leadTime: number | null }>,
  matrix: { flags: Array<{ kind: string; note: string }> },
): string {
  const parts: string[] = [];
  const winBase = winner.baseCents != null ? `$${(winner.baseCents / 100).toLocaleString()}` : "—";
  parts.push(`${winner.name} has the lowest base bid at ${winBase}.`);
  if (ranking.length > 1) {
    const second = ranking[1]!;
    const delta =
      winner.baseCents != null && second.baseCents != null
        ? `$${((second.baseCents - winner.baseCents) / 100).toLocaleString()}`
        : "—";
    parts.push(`Next lowest is ${second.name} (${delta} more).`);
  }
  if (winner.leadTime != null) parts.push(`Lead time ${winner.leadTime}w.`);
  const outlierFlags = matrix.flags.filter((f) => f.kind === "outlier").length;
  if (outlierFlags > 0) parts.push(`Note: ${outlierFlags} outlier line(s) flagged — review before accepting.`);
  return parts.join(" ");
}
