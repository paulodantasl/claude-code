import { router } from "../trpc.js";
import { authRouter } from "./auth.js";
import { projectRouter } from "./project.js";
import { documentRouter } from "./document.js";
import { chatRouter } from "./chat.js";

export const appRouter = router({
  auth: authRouter,
  project: projectRouter,
  document: documentRouter,
  chat: chatRouter,
});

export type AppRouter = typeof appRouter;
