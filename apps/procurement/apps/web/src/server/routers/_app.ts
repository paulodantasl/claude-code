import { router } from "../trpc.js";
import { authRouter } from "./auth.js";
import { projectRouter } from "./project.js";
import { documentRouter } from "./document.js";
import { chatRouter } from "./chat.js";
import { packageRouter } from "./package.js";
import { rfqRouter } from "./rfq.js";

export const appRouter = router({
  auth: authRouter,
  project: projectRouter,
  document: documentRouter,
  chat: chatRouter,
  package: packageRouter,
  rfq: rfqRouter,
});

export type AppRouter = typeof appRouter;
