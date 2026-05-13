import { z } from "zod";
import { and, desc, eq, inArray } from "drizzle-orm";
import { TRPCError } from "@trpc/server";
import { auditEvents, memberships, projects } from "@procurement/db";
import { db } from "@/lib/db";
import { recordAudit } from "@/lib/audit";
import { router, authedProcedure, projectProcedure } from "../trpc.js";

export const projectRouter = router({
  list: authedProcedure.query(async ({ ctx }) => {
    const orgIds = ctx.session.organizations.map((o) => o.id);
    if (orgIds.length === 0) return [];
    return db
      .select()
      .from(projects)
      .where(inArray(projects.organizationId, orgIds))
      .orderBy(desc(projects.createdAt));
  }),

  create: authedProcedure
    .input(
      z.object({
        organizationId: z.string().uuid(),
        name: z.string().min(1).max(200),
        jurisdiction: z.string().max(200).optional(),
        notes: z.string().max(2000).optional(),
      }),
    )
    .mutation(async ({ ctx, input }) => {
      const orgMatch = ctx.session.organizations.find(
        (o) => o.id === input.organizationId,
      );
      if (!orgMatch) {
        throw new TRPCError({ code: "FORBIDDEN", message: "Not a member of that organization." });
      }
      if (orgMatch.role === "pm_read_only") {
        throw new TRPCError({ code: "FORBIDDEN", message: "Read-only role." });
      }
      const [proj] = await db
        .insert(projects)
        .values({
          organizationId: input.organizationId,
          name: input.name,
          jurisdiction: input.jurisdiction,
          notes: input.notes,
          createdBy: ctx.session.userId,
        })
        .returning();
      await recordAudit({
        organizationId: input.organizationId,
        projectId: proj.id,
        userId: ctx.session.userId,
        action: "project.create",
        targetType: "project",
        targetId: proj.id,
        metadata: { name: proj.name },
      });
      return proj;
    }),

  get: projectProcedure.query(async ({ ctx }) => ({
    project: ctx.project,
    role: ctx.role,
  })),

  audit: projectProcedure.query(async ({ ctx }) => {
    return db
      .select()
      .from(auditEvents)
      .where(eq(auditEvents.projectId, ctx.project.id))
      .orderBy(desc(auditEvents.createdAt))
      .limit(100);
  }),
});
