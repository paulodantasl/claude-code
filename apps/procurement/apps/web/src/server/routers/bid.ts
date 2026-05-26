import { z } from "zod";
import { and, asc, desc, eq } from "drizzle-orm";
import { TRPCError } from "@trpc/server";
import {
  bids,
  documents,
  documentChunks,
  vendors,
  type BidLineItem,
} from "@procurement/db";
import { selectExtractor, type ExtractedLineItem } from "@procurement/llm";
import { db } from "@/lib/db";
import { env } from "@/lib/env";
import { recordAudit } from "@/lib/audit";
import { router, projectProcedure, writeProjectProcedure } from "../trpc";

const extractor = selectExtractor({
  apiKey: env.ANTHROPIC_API_KEY,
  model: env.ANTHROPIC_MODEL,
});

export const bidRouter = router({
  list: projectProcedure
    .input(z.object({ projectId: z.string().uuid(), packageId: z.string().uuid().optional() }))
    .query(async ({ ctx, input }) => {
      const conds = [eq(bids.projectId, ctx.project.id)];
      if (input.packageId) conds.push(eq(bids.packageId, input.packageId));
      const rows = await db
        .select({
          bid: bids,
          vendor: vendors,
          document: documents,
        })
        .from(bids)
        .innerJoin(vendors, eq(vendors.id, bids.vendorId))
        .innerJoin(documents, eq(documents.id, bids.documentId))
        .where(and(...conds))
        .orderBy(desc(bids.receivedAt));
      return rows;
    }),

  register: writeProjectProcedure
    .input(
      z.object({
        projectId: z.string().uuid(),
        packageId: z.string().uuid().optional(),
        vendorId: z.string().uuid(),
        documentId: z.string().uuid(),
      }),
    )
    .mutation(async ({ ctx, input }) => {
      const doc = (
        await db
          .select()
          .from(documents)
          .where(and(eq(documents.id, input.documentId), eq(documents.projectId, ctx.project.id)))
          .limit(1)
      )[0];
      if (!doc) throw new TRPCError({ code: "NOT_FOUND", message: "Document not in project" });

      const vendor = (
        await db
          .select()
          .from(vendors)
          .where(
            and(
              eq(vendors.id, input.vendorId),
              eq(vendors.organizationId, ctx.project.organizationId),
            ),
          )
          .limit(1)
      )[0];
      if (!vendor) throw new TRPCError({ code: "NOT_FOUND", message: "Vendor not in org" });

      try {
        const [bid] = await db
          .insert(bids)
          .values({
            projectId: ctx.project.id,
            packageId: input.packageId,
            vendorId: input.vendorId,
            documentId: input.documentId,
          })
          .returning();
        if (!bid) throw new TRPCError({ code: "INTERNAL_SERVER_ERROR", message: "Insert failed." });
        await recordAudit({
          organizationId: ctx.project.organizationId,
          projectId: ctx.project.id,
          userId: ctx.session.userId,
          action: "bid.register",
          targetType: "bid",
          targetId: bid.id,
          metadata: { vendorId: vendor.id, documentId: doc.id },
        });
        return bid;
      } catch (err) {
        if (err instanceof Error && /bids_document_idx/.test(err.message)) {
          throw new TRPCError({
            code: "CONFLICT",
            message: "This document is already registered as a bid.",
          });
        }
        throw err;
      }
    }),

  extract: writeProjectProcedure
    .input(z.object({ projectId: z.string().uuid(), bidId: z.string().uuid() }))
    .mutation(async ({ ctx, input }) => {
      const rows = await db
        .select({ bid: bids, document: documents })
        .from(bids)
        .innerJoin(documents, eq(documents.id, bids.documentId))
        .where(and(eq(bids.id, input.bidId), eq(bids.projectId, ctx.project.id)))
        .limit(1);
      const row = rows[0];
      if (!row) throw new TRPCError({ code: "NOT_FOUND" });
      if (row.document.status !== "parsed") {
        throw new TRPCError({
          code: "PRECONDITION_FAILED",
          message: `Document is ${row.document.status}; wait for parsing to complete.`,
        });
      }

      const chunks = await db
        .select()
        .from(documentChunks)
        .where(eq(documentChunks.documentId, row.document.id))
        .orderBy(asc(documentChunks.page), asc(documentChunks.chunkIndex));

      if (chunks.length === 0) {
        throw new TRPCError({
          code: "PRECONDITION_FAILED",
          message: "Bid document has no parsed text.",
        });
      }

      const bidText = chunks
        .map((c) => `[page ${c.page}]\n${c.text}`)
        .join("\n\n");

      const extracted = await extractor.extract({
        bidText,
        documentTitle: row.document.title,
      });

      // Map extractor output → BidLineItem with real chunk ids.
      const chunksByPage = new Map<number, typeof chunks>();
      for (const c of chunks) {
        const arr = chunksByPage.get(c.page) ?? [];
        arr.push(c);
        chunksByPage.set(c.page, arr);
      }

      const lineItems: BidLineItem[] = extracted.lineItems.map((li, i) =>
        normalize(li, i, chunksByPage),
      );

      const [updated] = await db
        .update(bids)
        .set({
          lineItems,
          // DB column is base_total_cents — convert dollars from extractor.
          baseTotal:
            extracted.baseTotal != null ? Math.round(extracted.baseTotal * 100) : null,
          leadTimeWeeks: extracted.leadTimeWeeks ?? null,
          extractedAt: new Date(),
          extractedBy: ctx.session.userId,
          status: "under_review",
        })
        .where(eq(bids.id, row.bid.id))
        .returning();

      await recordAudit({
        organizationId: ctx.project.organizationId,
        projectId: ctx.project.id,
        userId: ctx.session.userId,
        action: "bid.extracted",
        targetType: "bid",
        targetId: row.bid.id,
        metadata: {
          itemCount: lineItems.length,
          extractor: env.ANTHROPIC_API_KEY ? "anthropic" : "stub",
          assumptions: extracted.assumptions,
        },
      });
      return { bid: updated, assumptions: extracted.assumptions };
    }),

  setStatus: writeProjectProcedure
    .input(
      z.object({
        projectId: z.string().uuid(),
        bidId: z.string().uuid(),
        status: z.enum(["received", "under_review", "excluded", "accepted"]),
      }),
    )
    .mutation(async ({ ctx, input }) => {
      const [updated] = await db
        .update(bids)
        .set({ status: input.status })
        .where(and(eq(bids.id, input.bidId), eq(bids.projectId, ctx.project.id)))
        .returning();
      if (!updated) throw new TRPCError({ code: "NOT_FOUND" });
      await recordAudit({
        organizationId: ctx.project.organizationId,
        projectId: ctx.project.id,
        userId: ctx.session.userId,
        action: "bid.status_changed",
        targetType: "bid",
        targetId: updated.id,
        metadata: { status: input.status },
      });
      return updated;
    }),
});

function normalize(
  li: ExtractedLineItem,
  idx: number,
  chunksByPage: Map<number, Array<{ id: string; text: string; page: number }>>,
): BidLineItem {
  const pageChunks = li.sourcePage ? chunksByPage.get(li.sourcePage) ?? [] : [];
  // Pick the chunk that best contains the snippet, else the first chunk on the page.
  let chunkId: string | null = null;
  let snippet: string | null = null;
  if (li.sourceSnippet && pageChunks.length > 0) {
    const needle = li.sourceSnippet.slice(0, 60).toLowerCase();
    const match = pageChunks.find((c) => c.text.toLowerCase().includes(needle));
    chunkId = (match ?? pageChunks[0])?.id ?? null;
    snippet = li.sourceSnippet;
  } else if (pageChunks.length > 0) {
    chunkId = pageChunks[0]!.id;
    snippet = pageChunks[0]!.text.slice(0, 200);
  }
  return {
    id: `li-${idx}-${crypto.randomUUID().slice(0, 8)}`,
    description: li.description,
    qty: li.qty,
    unit: li.unit,
    unitPrice: li.unitPrice,
    extended: li.extended,
    category: li.category,
    notes: li.notes,
    source:
      li.sourcePage && chunkId
        ? { page: li.sourcePage, chunkId, snippet: snippet ?? "" }
        : null,
  };
}

