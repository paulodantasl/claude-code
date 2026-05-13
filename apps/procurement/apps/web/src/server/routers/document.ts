import { z } from "zod";
import { and, desc, eq } from "drizzle-orm";
import { TRPCError } from "@trpc/server";
import { documents, documentChunks, documentScans } from "@procurement/db";
import { db } from "@/lib/db";
import { createUploadUrl, createDownloadUrl, headObject } from "@/lib/storage";
import { enqueueParse } from "@/lib/queue";
import { recordAudit } from "@/lib/audit";
import { sha256 } from "@/lib/crypto";
import { router, projectProcedure, writeProjectProcedure } from "../trpc.js";

const ALLOWED_MIME = new Set([
  "application/pdf",
  "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
  "application/vnd.ms-excel",
]);

export const documentRouter = router({
  list: projectProcedure.query(async ({ ctx }) => {
    return db
      .select()
      .from(documents)
      .where(eq(documents.projectId, ctx.project.id))
      .orderBy(desc(documents.uploadedAt));
  }),

  // 1) Web asks for a signed upload URL.
  requestUpload: writeProjectProcedure
    .input(
      z.object({
        projectId: z.string().uuid(),
        title: z.string().min(1).max(300),
        mimeType: z.string().min(1).max(128),
        sizeBytes: z.number().int().positive().max(200 * 1024 * 1024),
        kind: z
          .enum([
            "spec",
            "addendum",
            "drawing_index",
            "bid",
            "submittal",
            "sds",
            "warranty",
            "coi",
            "lien_waiver",
            "other",
          ])
          .default("other"),
      }),
    )
    .mutation(async ({ ctx, input }) => {
      if (!ALLOWED_MIME.has(input.mimeType)) {
        throw new TRPCError({
          code: "BAD_REQUEST",
          message: `Unsupported file type: ${input.mimeType}`,
        });
      }
      const storageKey = `projects/${ctx.project.id}/${crypto.randomUUID()}-${slug(input.title)}`;
      const { url, expiresIn } = await createUploadUrl({
        storageKey,
        contentType: input.mimeType,
      });
      return { storageKey, uploadUrl: url, expiresIn };
    }),

  // 2) Web finalizes after PUT succeeds.
  finalizeUpload: writeProjectProcedure
    .input(
      z.object({
        projectId: z.string().uuid(),
        storageKey: z.string().min(1),
        title: z.string().min(1).max(300),
        mimeType: z.string().min(1).max(128),
        kind: z
          .enum([
            "spec",
            "addendum",
            "drawing_index",
            "bid",
            "submittal",
            "sds",
            "warranty",
            "coi",
            "lien_waiver",
            "other",
          ])
          .default("other"),
      }),
    )
    .mutation(async ({ ctx, input }) => {
      const head = await headObject(input.storageKey).catch(() => null);
      if (!head?.ContentLength) {
        throw new TRPCError({ code: "BAD_REQUEST", message: "Object not found in storage." });
      }
      const fakeSha = sha256(`${ctx.project.id}:${input.storageKey}:${head.ContentLength}`);
      const [doc] = await db
        .insert(documents)
        .values({
          projectId: ctx.project.id,
          title: input.title,
          mimeType: input.mimeType,
          sizeBytes: head.ContentLength,
          storageKey: input.storageKey,
          sha256: fakeSha,
          kind: input.kind,
          status: "scanning",
          uploadedBy: ctx.session.userId,
        })
        .returning();
      // Stubbed virus scan — flips to clean immediately and queues parse.
      await db.insert(documentScans).values({
        documentId: doc.id,
        clean: true,
        scanner: "stub",
      });
      await db
        .update(documents)
        .set({ status: "parsing" })
        .where(eq(documents.id, doc.id));
      await enqueueParse({
        documentId: doc.id,
        storageKey: doc.storageKey,
        mimeType: doc.mimeType,
      });
      await recordAudit({
        organizationId: ctx.project.organizationId,
        projectId: ctx.project.id,
        userId: ctx.session.userId,
        action: "document.upload",
        targetType: "document",
        targetId: doc.id,
        metadata: { title: doc.title, sizeBytes: doc.sizeBytes, kind: doc.kind },
      });
      return doc;
    }),

  downloadUrl: projectProcedure
    .input(z.object({ projectId: z.string().uuid(), documentId: z.string().uuid() }))
    .query(async ({ ctx, input }) => {
      const doc = (
        await db
          .select()
          .from(documents)
          .where(and(eq(documents.id, input.documentId), eq(documents.projectId, ctx.project.id)))
          .limit(1)
      )[0];
      if (!doc) throw new TRPCError({ code: "NOT_FOUND" });
      const url = await createDownloadUrl(doc.storageKey);
      return { url };
    }),

  get: projectProcedure
    .input(z.object({ projectId: z.string().uuid(), documentId: z.string().uuid() }))
    .query(async ({ ctx, input }) => {
      const doc = (
        await db
          .select()
          .from(documents)
          .where(and(eq(documents.id, input.documentId), eq(documents.projectId, ctx.project.id)))
          .limit(1)
      )[0];
      if (!doc) throw new TRPCError({ code: "NOT_FOUND" });
      return doc;
    }),

  chunksForPage: projectProcedure
    .input(
      z.object({
        projectId: z.string().uuid(),
        documentId: z.string().uuid(),
        page: z.number().int().min(1),
      }),
    )
    .query(async ({ ctx, input }) => {
      const doc = (
        await db
          .select()
          .from(documents)
          .where(and(eq(documents.id, input.documentId), eq(documents.projectId, ctx.project.id)))
          .limit(1)
      )[0];
      if (!doc) throw new TRPCError({ code: "NOT_FOUND" });
      return db
        .select()
        .from(documentChunks)
        .where(and(eq(documentChunks.documentId, doc.id), eq(documentChunks.page, input.page)));
    }),
});

function slug(s: string): string {
  return s
    .toLowerCase()
    .replace(/[^a-z0-9.-]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 80) || "file";
}
