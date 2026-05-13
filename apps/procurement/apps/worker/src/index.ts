import { Worker, type Job } from "bullmq";
import { PARSE_QUEUE, type ParseDocumentJob } from "@procurement/shared";
import { loadEnv } from "@procurement/shared/env";
import { runParseJob } from "./jobs/parseDocument.js";

const env = loadEnv();

const worker = new Worker<ParseDocumentJob>(
  PARSE_QUEUE,
  async (job: Job<ParseDocumentJob>) => runParseJob(job.data),
  {
    connection: { url: env.REDIS_URL },
    concurrency: 2,
  },
);

worker.on("ready", () => console.log("[worker] ready, queue:", PARSE_QUEUE));
worker.on("completed", (job) => console.log(`[worker] completed ${job.id}`));
worker.on("failed", (job, err) => console.error(`[worker] failed ${job?.id}:`, err.message));

const shutdown = async () => {
  console.log("[worker] shutting down…");
  await worker.close();
  process.exit(0);
};
process.on("SIGINT", shutdown);
process.on("SIGTERM", shutdown);
