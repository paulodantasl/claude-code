import { z } from "zod";
import { router, publicProcedure, authedProcedure } from "../trpc";
import { createMagicLink, endSession } from "@/lib/auth";
import { sendMagicLink } from "@/lib/mail";
import { recordAudit } from "@/lib/audit";

export const authRouter = router({
  requestMagicLink: publicProcedure
    .input(z.object({ email: z.string().email() }))
    .mutation(async ({ input }) => {
      const url = await createMagicLink(input.email);
      await sendMagicLink({ to: input.email, url });
      return { sent: true };
    }),

  me: authedProcedure.query(({ ctx }) => ctx.session),

  signOut: authedProcedure.mutation(async ({ ctx }) => {
    await recordAudit({
      userId: ctx.session.userId,
      action: "auth.sign_out",
    });
    await endSession();
    return { ok: true };
  }),
});
