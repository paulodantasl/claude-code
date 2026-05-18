import { z } from "zod";
import { asc, eq, inArray } from "drizzle-orm";
import { TRPCError } from "@trpc/server";
import { vendors } from "@procurement/db";
import { db } from "@/lib/db";
import { recordAudit } from "@/lib/audit";
import { router, authedProcedure } from "../trpc.js";

export const vendorRouter = router({
  list: authedProcedure
    .input(z.object({ organizationId: z.string().uuid() }))
    .query(async ({ ctx, input }) => {
      if (!ctx.session.organizations.some((o) => o.id === input.organizationId)) {
        throw new TRPCError({ code: "FORBIDDEN" });
      }
      return db
        .select()
        .from(vendors)
        .where(eq(vendors.organizationId, input.organizationId))
        .orderBy(asc(vendors.name));
    }),

  create: authedProcedure
    .input(
      z.object({
        organizationId: z.string().uuid(),
        name: z.string().min(1).max(200),
        contactName: z.string().max(200).optional(),
        contactEmail: z.string().email().optional(),
        trades: z.array(z.string()).default([]),
      }),
    )
    .mutation(async ({ ctx, input }) => {
      const match = ctx.session.organizations.find((o) => o.id === input.organizationId);
      if (!match) throw new TRPCError({ code: "FORBIDDEN" });
      if (match.role === "pm_read_only") {
        throw new TRPCError({ code: "FORBIDDEN", message: "Read-only role." });
      }
      const [vendor] = await db
        .insert(vendors)
        .values({
          organizationId: input.organizationId,
          name: input.name,
          contactName: input.contactName,
          contactEmail: input.contactEmail,
          trades: input.trades,
        })
        .returning();
      await recordAudit({
        organizationId: input.organizationId,
        userId: ctx.session.userId,
        action: "vendor.create",
        targetType: "vendor",
        targetId: vendor.id,
        metadata: { name: vendor.name },
      });
      return vendor;
    }),
});
