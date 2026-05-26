import { router } from "../trpc";
import { authRouter } from "./auth";
import { projectRouter } from "./project";
import { documentRouter } from "./document";
import { chatRouter } from "./chat";
import { packageRouter } from "./package";
import { rfqRouter } from "./rfq";
import { vendorRouter } from "./vendor";
import { bidRouter } from "./bid";
import { comparisonRouter } from "./comparison";
import { requirementRouter } from "./requirement";

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
  requirement: requirementRouter,
});

export type AppRouter = typeof appRouter;
