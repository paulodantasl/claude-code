import { z } from "zod";
import { and, asc, desc, eq, inArray, max } from "drizzle-orm";
import { TRPCError } from "@trpc/server";
import {
  documents,
  packages,
  rfqDraftVersions,
  rfqDrafts,
  rfqExports,
  rfqTemplates,
  type FilledSection,
} from "@procurement/db";
import { db } from "@/lib/db";
import { recordAudit } from "@/lib/audit";
import { createDownloadUrl, s3Client, BUCKET } from "@/lib/storage";
import { PutObjectCommand } from "@aws-sdk/client-s3";
import { generateRfqSection } from "../rfq-generator";
import { renderRfqDocx } from "../rfq-export";
import { router, projectProcedure, writeProjectProcedure } from "../trpc";

async function loadDraft(projectId: string, draftId: string) {
  const draft = (
    await db
      .select()
      .from(rfqDrafts)
      .where(and(eq(rfqDrafts.id, draftId), eq(rfqDrafts.projectId, projectId)))
      .limit(1)
  )[0];
  if (!draft) throw new TRPCError({ code: "NOT_FOUND" });
  return draft;
}

export const rfqRouter = router({
  listTemplates: projectProcedure.query(async () => {
    return db.select().from(rfqTemplates).orderBy(asc(rfqTemplates.name));
  }),

  listDrafts: projectProcedure
    .input(z.object({ projectId: z.string().uuid(), packageId: z.string().uuid().optional() }))
    .query(async ({ ctx, input }) => {
      const conds = [eq(rfqDrafts.projectId, ctx.project.id)];
      if (input.packageId) conds.push(eq(rfqDrafts.packageId, input.packageId));
      return db
        .select()
        .from(rfqDrafts)
        .where(and(...conds))
        .orderBy(desc(rfqDrafts.updatedAt));
    }),

  createDraft: writeProjectProcedure
    .input(
      z.object({
        projectId: z.string().uuid(),
        templateId: z.string().uuid(),
        packageId: z.string().uuid().optional(),
        title: z.string().min(1).max(200),
      }),
    )
    .mutation(async ({ ctx, input }) => {
      const tpl = (
        await db.select().from(rfqTemplates).where(eq(rfqTemplates.id, input.templateId)).limit(1)
      )[0];
      if (!tpl) throw new TRPCError({ code: "NOT_FOUND", message: "Template not found" });

      if (input.packageId) {
        const pkg = (
          await db
            .select()
            .from(packages)
            .where(and(eq(packages.id, input.packageId), eq(packages.projectId, ctx.project.id)))
            .limit(1)
        )[0];
        if (!pkg) throw new TRPCError({ code: "NOT_FOUND", message: "Package not found in project" });
      }

      const empty: FilledSection[] = tpl.sections.map((s) => ({
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
          projectId: ctx.project.id,
          packageId: input.packageId,
          templateId: tpl.id,
          title: input.title,
          currentSections: empty,
          createdBy: ctx.session.userId,
        })
        .returning();
      if (!draft) throw new TRPCError({ code: "INTERNAL_SERVER_ERROR", message: "Insert failed." });
      await recordAudit({
        organizationId: ctx.project.organizationId,
        projectId: ctx.project.id,
        userId: ctx.session.userId,
        action: "rfq.draft_created",
        targetType: "rfq_draft",
        targetId: draft.id,
        metadata: { title: draft.title, templateId: tpl.id, sections: empty.length },
      });
      return draft;
    }),

  getDraft: projectProcedure
    .input(z.object({ projectId: z.string().uuid(), draftId: z.string().uuid() }))
    .query(async ({ ctx, input }) => {
      const draft = await loadDraft(ctx.project.id, input.draftId);
      const tpl = (
        await db.select().from(rfqTemplates).where(eq(rfqTemplates.id, draft.templateId)).limit(1)
      )[0];
      const versions = await db
        .select({
          id: rfqDraftVersions.id,
          versionNumber: rfqDraftVersions.versionNumber,
          notes: rfqDraftVersions.notes,
          createdAt: rfqDraftVersions.createdAt,
        })
        .from(rfqDraftVersions)
        .where(eq(rfqDraftVersions.draftId, draft.id))
        .orderBy(desc(rfqDraftVersions.versionNumber));
      return { draft, template: tpl, versions };
    }),

  generateSection: writeProjectProcedure
    .input(
      z.object({
        projectId: z.string().uuid(),
        draftId: z.string().uuid(),
        sectionId: z.string().min(1),
      }),
    )
    .mutation(async ({ ctx, input }) => {
      const draft = await loadDraft(ctx.project.id, input.draftId);
      const tpl = (
        await db.select().from(rfqTemplates).where(eq(rfqTemplates.id, draft.templateId)).limit(1)
      )[0];
      if (!tpl) throw new TRPCError({ code: "NOT_FOUND", message: "Template gone" });
      const spec = tpl.sections.find((s) => s.id === input.sectionId);
      if (!spec) {
        throw new TRPCError({ code: "BAD_REQUEST", message: "Unknown section id" });
      }

      const filled = await generateRfqSection({
        projectId: ctx.project.id,
        userId: ctx.session.userId,
        section: spec,
        rfqTitle: draft.title,
        projectName: ctx.project.name,
      });

      const merged = draft.currentSections.map((s) => (s.id === filled.id ? filled : s));
      // If section wasn't pre-seeded (template added later), append.
      if (!merged.some((s) => s.id === filled.id)) merged.push(filled);

      const [updated] = await db
        .update(rfqDrafts)
        .set({ currentSections: merged, updatedAt: new Date() })
        .where(eq(rfqDrafts.id, draft.id))
        .returning();

      await recordAudit({
        organizationId: ctx.project.organizationId,
        projectId: ctx.project.id,
        userId: ctx.session.userId,
        action: "rfq.section_generated",
        targetType: "rfq_draft",
        targetId: draft.id,
        metadata: {
          sectionId: input.sectionId,
          citationCount: filled.citations.length,
          bodyLength: filled.body.length,
        },
      });

      return { draft: updated, section: filled };
    }),

  updateSection: writeProjectProcedure
    .input(
      z.object({
        projectId: z.string().uuid(),
        draftId: z.string().uuid(),
        sectionId: z.string().min(1),
        body: z.string().max(50_000),
      }),
    )
    .mutation(async ({ ctx, input }) => {
      const draft = await loadDraft(ctx.project.id, input.draftId);
      const merged = draft.currentSections.map((s) =>
        s.id === input.sectionId
          ? { ...s, body: input.body, editedAt: new Date().toISOString() }
          : s,
      );
      const [updated] = await db
        .update(rfqDrafts)
        .set({ currentSections: merged, updatedAt: new Date() })
        .where(eq(rfqDrafts.id, draft.id))
        .returning();
      return updated;
    }),

  saveVersion: writeProjectProcedure
    .input(
      z.object({
        projectId: z.string().uuid(),
        draftId: z.string().uuid(),
        notes: z.string().max(500).optional(),
      }),
    )
    .mutation(async ({ ctx, input }) => {
      const draft = await loadDraft(ctx.project.id, input.draftId);
      const [latest] = await db
        .select({ max: max(rfqDraftVersions.versionNumber) })
        .from(rfqDraftVersions)
        .where(eq(rfqDraftVersions.draftId, draft.id));
      const next = (latest?.max ?? 0) + 1;
      const [version] = await db
        .insert(rfqDraftVersions)
        .values({
          draftId: draft.id,
          versionNumber: next,
          sections: draft.currentSections,
          notes: input.notes,
          createdBy: ctx.session.userId,
        })
        .returning();
      if (!version) throw new TRPCError({ code: "INTERNAL_SERVER_ERROR", message: "Insert failed." });
      await recordAudit({
        organizationId: ctx.project.organizationId,
        projectId: ctx.project.id,
        userId: ctx.session.userId,
        action: "rfq.version_saved",
        targetType: "rfq_draft",
        targetId: draft.id,
        metadata: { versionId: version.id, versionNumber: version.versionNumber },
      });
      return version;
    }),

  getVersion: projectProcedure
    .input(z.object({ projectId: z.string().uuid(), versionId: z.string().uuid() }))
    .query(async ({ ctx, input }) => {
      const rows = await db
        .select({ version: rfqDraftVersions, draft: rfqDrafts })
        .from(rfqDraftVersions)
        .innerJoin(rfqDrafts, eq(rfqDrafts.id, rfqDraftVersions.draftId))
        .where(
          and(
            eq(rfqDraftVersions.id, input.versionId),
            eq(rfqDrafts.projectId, ctx.project.id),
          ),
        )
        .limit(1);
      const row = rows[0];
      if (!row) throw new TRPCError({ code: "NOT_FOUND" });
      return row;
    }),

  exportVersion: writeProjectProcedure
    .input(
      z.object({
        projectId: z.string().uuid(),
        versionId: z.string().uuid(),
        format: z.enum(["docx"]),
      }),
    )
    .mutation(async ({ ctx, input }) => {
      const rows = await db
        .select({ version: rfqDraftVersions, draft: rfqDrafts })
        .from(rfqDraftVersions)
        .innerJoin(rfqDrafts, eq(rfqDrafts.id, rfqDraftVersions.draftId))
        .where(
          and(
            eq(rfqDraftVersions.id, input.versionId),
            eq(rfqDrafts.projectId, ctx.project.id),
          ),
        )
        .limit(1);
      const row = rows[0];
      if (!row) throw new TRPCError({ code: "NOT_FOUND" });

      const citedDocIds = Array.from(
        new Set(
          row.version.sections.flatMap((s) => s.citations.map((c) => c.documentId)),
        ),
      );
      const titlesMap: Record<string, string> = {};
      if (citedDocIds.length > 0) {
        const docs = await db
          .select({ id: documents.id, title: documents.title })
          .from(documents)
          .where(inArray(documents.id, citedDocIds));
        for (const d of docs) titlesMap[d.id] = d.title;
      }

      const buf = await renderRfqDocx({
        rfqTitle: row.draft.title,
        projectName: ctx.project.name,
        versionNumber: row.version.versionNumber,
        sections: row.version.sections,
        documentTitles: titlesMap,
      });

      const storageKey = `projects/${ctx.project.id}/rfq-exports/${row.version.id}-v${row.version.versionNumber}.docx`;
      await s3Client.send(
        new PutObjectCommand({
          Bucket: BUCKET,
          Key: storageKey,
          Body: buf,
          ContentType:
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        }),
      );
      const [record] = await db
        .insert(rfqExports)
        .values({
          versionId: row.version.id,
          format: "docx",
          storageKey,
          sizeBytes: buf.byteLength,
          createdBy: ctx.session.userId,
        })
        .returning();
      if (!record) throw new TRPCError({ code: "INTERNAL_SERVER_ERROR", message: "Insert failed." });
      const url = await createDownloadUrl(storageKey);
      await recordAudit({
        organizationId: ctx.project.organizationId,
        projectId: ctx.project.id,
        userId: ctx.session.userId,
        action: "rfq.exported",
        targetType: "rfq_export",
        targetId: record.id,
        metadata: {
          versionId: row.version.id,
          format: "docx",
          sizeBytes: buf.byteLength,
        },
      });
      return { url, sizeBytes: buf.byteLength, format: "docx" as const };
    }),
});
