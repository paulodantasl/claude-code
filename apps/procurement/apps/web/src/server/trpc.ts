import { initTRPC, TRPCError } from "@trpc/server";
import superjson from "superjson";
import { z } from "zod";
import { and, eq } from "drizzle-orm";
import { memberships, projects } from "@procurement/db";
import { db } from "@/lib/db";
import { getSession, type SessionContext } from "@/lib/auth";

export interface TrpcContext {
  session: SessionContext | null;
}

export async function createContext(): Promise<TrpcContext> {
  const session = await getSession();
  return { session };
}

const t = initTRPC.context<TrpcContext>().create({
  transformer: superjson,
  errorFormatter: ({ shape }) => shape,
});

export const router = t.router;
export const publicProcedure = t.procedure;

export const authedProcedure = t.procedure.use(({ ctx, next }) => {
  if (!ctx.session) {
    throw new TRPCError({ code: "UNAUTHORIZED" });
  }
  return next({ ctx: { ...ctx, session: ctx.session } });
});

// Procedure that verifies the user is a member of the project's org.
export const projectProcedure = authedProcedure
  .input(z.object({ projectId: z.string().uuid() }))
  .use(async ({ ctx, input, next }) => {
    const rows = await db
      .select({
        project: projects,
        role: memberships.role,
      })
      .from(projects)
      .innerJoin(
        memberships,
        and(
          eq(memberships.organizationId, projects.organizationId),
          eq(memberships.userId, ctx.session.userId),
        ),
      )
      .where(eq(projects.id, input.projectId))
      .limit(1);
    const row = rows[0];
    if (!row) {
      throw new TRPCError({
        code: "FORBIDDEN",
        message: "You don't have access to this project.",
      });
    }
    return next({
      ctx: {
        ...ctx,
        project: row.project,
        role: row.role,
      },
    });
  });

export const writeProjectProcedure = projectProcedure.use(({ ctx, next }) => {
  if (ctx.role === "pm_read_only") {
    throw new TRPCError({ code: "FORBIDDEN", message: "Read-only role." });
  }
  return next();
});
