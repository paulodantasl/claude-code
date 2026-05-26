import { z } from "zod";
import { and, asc, desc, eq, inArray } from "drizzle-orm";
import { TRPCError } from "@trpc/server";
import {
  documents,
  fulfillments,
  packages,
  requirementTemplates,
  requirements,
  type Requirement,
} from "@procurement/db";
import { selectDeriver } from "@procurement/llm";
import { db } from "@/lib/db";
import { env } from "@/lib/env";
import { recordAudit } from "@/lib/audit";
import { searchProjectDocs } from "../search.js";
import { router, projectProcedure, writeProjectProcedure } from "../trpc.js";

const deriver = selectDeriver({
  apiKey: env.ANTHROPIC_API_KEY,
  model: env.ANTHROPIC_MODEL,
});

const ARTIFACT_KINDS = [
  "submittal",
  "sds",
  "warranty",
  "coi",
  "lien_waiver",
  "other",
] as const;

// Attach the latest fulfillment (if any) to each requirement.
async function withFulfillments(reqs: Requirement[]) {
  if (reqs.length === 0) return [];
  const ful = await db
    .select()
    .from(fulfillments)
    .where(
      inArray(
        fulfillments.requirementId,
        reqs.map((r) => r.id),
      ),
    )
    .orderBy(desc(fulfillments.createdAt));
  const latestByReq = new Map<string, (typeof ful)[number]>();
  for (const f of ful) {
    if (!latestByReq.has(f.requirementId)) latestByReq.set(f.requirementId, f);
  }
  return reqs.map((r) => ({
    requirement: r,
    currentFulfillment: latestByReq.get(r.id) ?? null,
  }));
}

export const requirementRouter = router({
  listTemplates: projectProcedure.query(async () => {
    return db.select().from(requirementTemplates).orderBy(asc(requirementTemplates.name));
  }),

  list: projectProcedure
    .input(z.object({ projectId: z.string().uuid(), packageId: z.string().uuid() }))
    .query(async ({ ctx, input }) => {
      const reqs = await db
        .select()
        .from(requirements)
        .where(
          and(
            eq(requirements.projectId, ctx.project.id),
            eq(requirements.packageId, input.packageId),
          ),
        )
        .orderBy(asc(requirements.createdAt));
      return withFulfillments(reqs);
    }),

  gapReport: projectProcedure
    .input(z.object({ projectId: z.string().uuid(), packageId: z.string().uuid() }))
    .query(async ({ ctx, input }) => {
      const reqs = await db
        .select()
        .from(requirements)
        .where(
          and(
            eq(requirements.projectId, ctx.project.id),
            eq(requirements.packageId, input.packageId),
          ),
        );
      const counts = { missing: 0, received: 0, under_review: 0, approved: 0, rejected: 0 };
      let requiredOpen = 0;
      for (const r of reqs) {
        counts[r.status] += 1;
        if (r.severity === "required" && r.status !== "approved") requiredOpen += 1;
      }
      return { total: reqs.length, counts, requiredOpen };
    }),

  reviewerQueue: projectProcedure.query(async ({ ctx }) => {
    const reqs = await db
      .select({ requirement: requirements, packageName: packages.name })
      .from(requirements)
      .leftJoin(packages, eq(packages.id, requirements.packageId))
      .where(
        and(
          eq(requirements.projectId, ctx.project.id),
          inArray(requirements.status, ["received", "under_review"]),
        ),
      )
      .orderBy(asc(requirements.updatedAt));
    return reqs;
  }),

  addFromTemplate: writeProjectProcedure
    .input(
      z.object({
        projectId: z.string().uuid(),
        packageId: z.string().uuid(),
        templateId: z.string().uuid(),
      }),
    )
    .mutation(async ({ ctx, input }) => {
      const pkg = (
        await db
          .select()
          .from(packages)
          .where(and(eq(packages.id, input.packageId), eq(packages.projectId, ctx.project.id)))
          .limit(1)
      )[0];
      if (!pkg) throw new TRPCError({ code: "NOT_FOUND", message: "Package not found" });
      const tpl = (
        await db
          .select()
          .from(requirementTemplates)
          .where(eq(requirementTemplates.id, input.templateId))
          .limit(1)
      )[0];
      if (!tpl) throw new TRPCError({ code: "NOT_FOUND", message: "Template not found" });

      const inserted = await db
        .insert(requirements)
        .values(
          tpl.items.map((item) => ({
            projectId: ctx.project.id,
            packageId: input.packageId,
            label: item.label,
            description: item.description,
            artifactKind: item.artifactKind,
            severity: item.severity,
            sourceClause: item.sourceHint,
          })),
        )
        .returning();
      await recordAudit({
        organizationId: ctx.project.organizationId,
        projectId: ctx.project.id,
        userId: ctx.session.userId,
        action: "requirement.added_from_template",
        targetType: "package",
        targetId: input.packageId,
        metadata: { templateId: tpl.id, count: inserted.length },
      });
      return inserted;
    }),

  deriveFromSpec: writeProjectProcedure
    .input(
      z.object({
        projectId: z.string().uuid(),
        packageId: z.string().uuid(),
        query: z.string().min(1).max(300).default("submittals certificates warranties insurance requirements"),
      }),
    )
    .mutation(async ({ ctx, input }) => {
      const hits = await searchProjectDocs(ctx.project.id, input.query, 16);
      if (hits.length === 0) {
        throw new TRPCError({
          code: "PRECONDITION_FAILED",
          message: "No parsed spec text found to derive requirements from.",
        });
      }
      // Map page -> a representative source documentId for provenance.
      const docByPage = new Map<number, { documentId: string }>();
      for (const h of hits) {
        if (!docByPage.has(h.page)) docByPage.set(h.page, { documentId: h.documentId });
      }
      const specText = hits.map((h) => `[page ${h.page}]\n${h.snippet}`).join("\n\n");

      const derived = await deriver.derive({ specText });
      if (derived.requirements.length === 0) {
        return { inserted: [], note: "Model found no requirements in the retrieved text." };
      }

      const inserted = await db
        .insert(requirements)
        .values(
          derived.requirements.map((r) => ({
            projectId: ctx.project.id,
            packageId: input.packageId,
            label: r.label,
            description: r.description,
            artifactKind: r.artifactKind,
            severity: r.severity,
            sourceClause: r.sourceClause,
            sourceDocumentId: r.sourcePage
              ? docByPage.get(r.sourcePage)?.documentId ?? null
              : null,
            sourcePage: r.sourcePage,
            sourceSnippet: r.sourceSnippet,
          })),
        )
        .returning();
      await recordAudit({
        organizationId: ctx.project.organizationId,
        projectId: ctx.project.id,
        userId: ctx.session.userId,
        action: "requirement.derived_from_spec",
        targetType: "package",
        targetId: input.packageId,
        metadata: { count: inserted.length, query: input.query },
      });
      return { inserted, note: null };
    }),

  addManual: writeProjectProcedure
    .input(
      z.object({
        projectId: z.string().uuid(),
        packageId: z.string().uuid(),
        label: z.string().min(1).max(200),
        description: z.string().max(1000).optional(),
        artifactKind: z.enum(ARTIFACT_KINDS).default("submittal"),
        severity: z.enum(["required", "recommended", "optional"]).default("required"),
      }),
    )
    .mutation(async ({ ctx, input }) => {
      const [req] = await db
        .insert(requirements)
        .values({
          projectId: ctx.project.id,
          packageId: input.packageId,
          label: input.label,
          description: input.description,
          artifactKind: input.artifactKind,
          severity: input.severity,
        })
        .returning();
      return req;
    }),

  bindEvidence: writeProjectProcedure
    .input(
      z.object({
        projectId: z.string().uuid(),
        requirementId: z.string().uuid(),
        documentId: z.string().uuid(),
        page: z.number().int().min(1).optional(),
        note: z.string().max(1000).optional(),
      }),
    )
    .mutation(async ({ ctx, input }) => {
      const req = (
        await db
          .select()
          .from(requirements)
          .where(
            and(
              eq(requirements.id, input.requirementId),
              eq(requirements.projectId, ctx.project.id),
            ),
          )
          .limit(1)
      )[0];
      if (!req) throw new TRPCError({ code: "NOT_FOUND" });
      const doc = (
        await db
          .select()
          .from(documents)
          .where(and(eq(documents.id, input.documentId), eq(documents.projectId, ctx.project.id)))
          .limit(1)
      )[0];
      if (!doc) throw new TRPCError({ code: "NOT_FOUND", message: "Evidence document not in project" });

      await db.insert(fulfillments).values({
        requirementId: req.id,
        evidenceDocumentId: doc.id,
        evidencePage: input.page,
        note: input.note,
        createdBy: ctx.session.userId,
      });
      const [updated] = await db
        .update(requirements)
        .set({ status: "received", updatedAt: new Date() })
        .where(eq(requirements.id, req.id))
        .returning();
      await recordAudit({
        organizationId: ctx.project.organizationId,
        projectId: ctx.project.id,
        userId: ctx.session.userId,
        action: "requirement.evidence_bound",
        targetType: "requirement",
        targetId: req.id,
        metadata: { documentId: doc.id, page: input.page ?? null },
      });
      return updated;
    }),

  review: writeProjectProcedure
    .input(
      z.object({
        projectId: z.string().uuid(),
        requirementId: z.string().uuid(),
        status: z.enum(["under_review", "approved", "rejected"]),
        notes: z.string().max(1000).optional(),
      }),
    )
    .mutation(async ({ ctx, input }) => {
      const [updated] = await db
        .update(requirements)
        .set({
          status: input.status,
          reviewerNotes: input.notes,
          reviewedBy: ctx.session.userId,
          reviewedAt: new Date(),
          updatedAt: new Date(),
        })
        .where(
          and(
            eq(requirements.id, input.requirementId),
            eq(requirements.projectId, ctx.project.id),
          ),
        )
        .returning();
      if (!updated) throw new TRPCError({ code: "NOT_FOUND" });
      await recordAudit({
        organizationId: ctx.project.organizationId,
        projectId: ctx.project.id,
        userId: ctx.session.userId,
        action: "requirement.reviewed",
        targetType: "requirement",
        targetId: updated.id,
        metadata: { status: input.status },
      });
      return updated;
    }),
});
