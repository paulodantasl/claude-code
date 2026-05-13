import { z } from "zod";
import { asc, desc, eq } from "drizzle-orm";
import { TRPCError } from "@trpc/server";
import { chatMessages, chatThreads } from "@procurement/db";
import { selectProvider, type ToolRegistry } from "@procurement/llm";
import { db } from "@/lib/db";
import { env } from "@/lib/env";
import { recordAudit } from "@/lib/audit";
import { searchProjectDocs, getPageText } from "../search.js";
import { router, projectProcedure, writeProjectProcedure } from "../trpc.js";

const provider = selectProvider({
  apiKey: env.ANTHROPIC_API_KEY,
  model: env.ANTHROPIC_MODEL,
});

export const chatRouter = router({
  listThreads: projectProcedure.query(async ({ ctx }) => {
    return db
      .select()
      .from(chatThreads)
      .where(eq(chatThreads.projectId, ctx.project.id))
      .orderBy(desc(chatThreads.updatedAt));
  }),

  createThread: writeProjectProcedure
    .input(z.object({ projectId: z.string().uuid(), title: z.string().min(1).max(200).optional() }))
    .mutation(async ({ ctx, input }) => {
      const [thread] = await db
        .insert(chatThreads)
        .values({
          projectId: ctx.project.id,
          createdBy: ctx.session.userId,
          title: input.title ?? "New thread",
        })
        .returning();
      return thread;
    }),

  getThread: projectProcedure
    .input(z.object({ projectId: z.string().uuid(), threadId: z.string().uuid() }))
    .query(async ({ ctx, input }) => {
      const thread = (
        await db
          .select()
          .from(chatThreads)
          .where(eq(chatThreads.id, input.threadId))
          .limit(1)
      )[0];
      if (!thread || thread.projectId !== ctx.project.id) {
        throw new TRPCError({ code: "NOT_FOUND" });
      }
      const messages = await db
        .select()
        .from(chatMessages)
        .where(eq(chatMessages.threadId, thread.id))
        .orderBy(asc(chatMessages.createdAt));
      return { thread, messages };
    }),

  sendMessage: writeProjectProcedure
    .input(
      z.object({
        projectId: z.string().uuid(),
        threadId: z.string().uuid(),
        message: z.string().min(1).max(4000),
      }),
    )
    .mutation(async ({ ctx, input }) => {
      const thread = (
        await db
          .select()
          .from(chatThreads)
          .where(eq(chatThreads.id, input.threadId))
          .limit(1)
      )[0];
      if (!thread || thread.projectId !== ctx.project.id) {
        throw new TRPCError({ code: "NOT_FOUND" });
      }

      const prior = await db
        .select()
        .from(chatMessages)
        .where(eq(chatMessages.threadId, thread.id))
        .orderBy(asc(chatMessages.createdAt));

      const [userMsg] = await db
        .insert(chatMessages)
        .values({
          threadId: thread.id,
          role: "user",
          content: input.message,
        })
        .returning();

      const tools: ToolRegistry = {
        search_project_docs: async (toolInput) =>
          ({
            hits: await searchProjectDocs(
              ctx.project.id,
              toolInput.query,
              toolInput.limit ?? 8,
            ),
          }),
        get_page_text: async (toolInput) =>
          getPageText(ctx.project.id, toolInput.documentId, toolInput.page),
      };

      const result = await provider.run({
        history: prior.map((m) => ({
          role: m.role === "assistant" ? "assistant" : "user",
          content: m.content,
        })),
        userMessage: input.message,
        tools,
        ctx: { projectId: ctx.project.id, userId: ctx.session.userId },
      });

      const [assistantMsg] = await db
        .insert(chatMessages)
        .values({
          threadId: thread.id,
          role: "assistant",
          content: result.reply,
          citations: result.citations,
          trace: result.trace as unknown as Record<string, unknown>,
        })
        .returning();

      await db
        .update(chatThreads)
        .set({ updatedAt: new Date() })
        .where(eq(chatThreads.id, thread.id));

      await recordAudit({
        organizationId: ctx.project.organizationId,
        projectId: ctx.project.id,
        userId: ctx.session.userId,
        action: "chat.message",
        targetType: "chat_thread",
        targetId: thread.id,
        metadata: {
          model: result.trace.model,
          toolCallCount: result.trace.toolCalls.length,
          citationCount: result.citations.length,
        },
      });

      return { userMessage: userMsg, assistantMessage: assistantMsg };
    }),
});
