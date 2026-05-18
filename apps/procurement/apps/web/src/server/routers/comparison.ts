import { z } from "zod";
import { and, desc, eq, inArray } from "drizzle-orm";
import { TRPCError } from "@trpc/server";
import { bids, comparisonRuns, vendors } from "@procurement/db";
import { db } from "@/lib/db";
import { recordAudit } from "@/lib/audit";
import { buildComparisonMatrix } from "../comparison-builder.js";
import { router, projectProcedure, writeProjectProcedure } from "../trpc.js";

export const comparisonRouter = router({
  list: projectProcedure
    .input(z.object({ projectId: z.string().uuid(), packageId: z.string().uuid().optional() }))
    .query(async ({ ctx, input }) => {
      const conds = [eq(comparisonRuns.projectId, ctx.project.id)];
      if (input.packageId) conds.push(eq(comparisonRuns.packageId, input.packageId));
      return db
        .select()
        .from(comparisonRuns)
        .where(and(...conds))
        .orderBy(desc(comparisonRuns.createdAt));
    }),

  get: projectProcedure
    .input(z.object({ projectId: z.string().uuid(), runId: z.string().uuid() }))
    .query(async ({ ctx, input }) => {
      const run = (
        await db
          .select()
          .from(comparisonRuns)
          .where(
            and(
              eq(comparisonRuns.id, input.runId),
              eq(comparisonRuns.projectId, ctx.project.id),
            ),
          )
          .limit(1)
      )[0];
      if (!run) throw new TRPCError({ code: "NOT_FOUND" });
      return run;
    }),

  create: writeProjectProcedure
    .input(
      z.object({
        projectId: z.string().uuid(),
        packageId: z.string().uuid().optional(),
        bidIds: z.array(z.string().uuid()).min(2).max(20),
        title: z.string().min(1).max(200),
      }),
    )
    .mutation(async ({ ctx, input }) => {
      const selected = await db
        .select({ bid: bids, vendor: vendors })
        .from(bids)
        .innerJoin(vendors, eq(vendors.id, bids.vendorId))
        .where(
          and(
            inArray(bids.id, input.bidIds),
            eq(bids.projectId, ctx.project.id),
          ),
        );
      if (selected.length !== input.bidIds.length) {
        throw new TRPCError({
          code: "BAD_REQUEST",
          message: "Some bids are missing or do not belong to this project.",
        });
      }
      const notExtracted = selected.filter(
        (s) => !s.bid.extractedAt || s.bid.lineItems.length === 0,
      );
      if (notExtracted.length > 0) {
        const names = notExtracted.map((b) => b.vendor.name).join(", ");
        throw new TRPCError({
          code: "PRECONDITION_FAILED",
          message: `Run extract on these bids first: ${names}.`,
        });
      }
      const matrix = buildComparisonMatrix({
        bids: selected.map((s) => ({ ...s.bid, vendor: s.vendor })),
      });
      const assumptions = [
        `${selected.length} vendors compared on ${matrix.rows.length} normalized lines.`,
        `Bids selected at ${new Date().toISOString()}.`,
        "Lines grouped by normalized description; review groupings manually for accuracy.",
      ];
      const [run] = await db
        .insert(comparisonRuns)
        .values({
          projectId: ctx.project.id,
          packageId: input.packageId,
          title: input.title,
          bidIds: input.bidIds,
          matrix,
          assumptions,
          createdBy: ctx.session.userId,
        })
        .returning();
      await recordAudit({
        organizationId: ctx.project.organizationId,
        projectId: ctx.project.id,
        userId: ctx.session.userId,
        action: "comparison.created",
        targetType: "comparison_run",
        targetId: run.id,
        metadata: {
          bidCount: selected.length,
          rowCount: matrix.rows.length,
          flagCount: matrix.flags.length,
        },
      });
      return run;
    }),
});
