import { z } from "zod";
import { and, desc, eq } from "drizzle-orm";
import { TRPCError } from "@trpc/server";
import { packages } from "@procurement/db";
import { db } from "@/lib/db";
import { recordAudit } from "@/lib/audit";
import { router, projectProcedure, writeProjectProcedure } from "../trpc.js";

export const packageRouter = router({
  list: projectProcedure.query(async ({ ctx }) => {
    return db
      .select()
      .from(packages)
      .where(eq(packages.projectId, ctx.project.id))
      .orderBy(desc(packages.createdAt));
  }),

  create: writeProjectProcedure
    .input(
      z.object({
        projectId: z.string().uuid(),
        kind: z.enum(["sourcing", "compliance"]),
        name: z.string().min(1).max(200),
        scopeNotes: z.string().max(2000).optional(),
        bidDueAt: z.date().optional(),
      }),
    )
    .mutation(async ({ ctx, input }) => {
      const [pkg] = await db
        .insert(packages)
        .values({
          projectId: ctx.project.id,
          kind: input.kind,
          name: input.name,
          scopeNotes: input.scopeNotes,
          bidDueAt: input.bidDueAt,
        })
        .returning();
      await recordAudit({
        organizationId: ctx.project.organizationId,
        projectId: ctx.project.id,
        userId: ctx.session.userId,
        action: "package.create",
        targetType: "package",
        targetId: pkg.id,
        metadata: { name: pkg.name, kind: pkg.kind },
      });
      return pkg;
    }),

  get: projectProcedure
    .input(z.object({ projectId: z.string().uuid(), packageId: z.string().uuid() }))
    .query(async ({ ctx, input }) => {
      const pkg = (
        await db
          .select()
          .from(packages)
          .where(and(eq(packages.id, input.packageId), eq(packages.projectId, ctx.project.id)))
          .limit(1)
      )[0];
      if (!pkg) throw new TRPCError({ code: "NOT_FOUND" });
      return pkg;
    }),
});
