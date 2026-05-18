import { router } from "../trpc.js";
import { authRouter } from "./auth.js";
import { projectRouter } from "./project.js";
import { documentRouter } from "./document.js";
import { chatRouter } from "./chat.js";
import { packageRouter } from "./package.js";
import { rfqRouter } from "./rfq.js";
import { vendorRouter } from "./vendor.js";
import { bidRouter } from "./bid.js";
import { comparisonRouter } from "./comparison.js";

export const appRouter = router({
  auth: authRouter,
  project: projectRouter,
  document: documentRouter,
  chat: chatRouter,
  package: packageRouter,
  rfq: rfqRouter,
  vendor: vendorRouter,
  bid: bidRouter,
  comparison: comparisonRouter,
});

export type AppRouter = typeof appRouter;
