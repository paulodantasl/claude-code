import { Queue } from "bullmq";
import { PARSE_QUEUE, type ParseDocumentJob } from "@procurement/shared";
import { env } from "./env";

const connection = { url: env.REDIS_URL };

let cached: Queue<ParseDocumentJob> | null = null;

export function parseQueue(): Queue<ParseDocumentJob> {
  if (!cached) {
    cached = new Queue<ParseDocumentJob>(PARSE_QUEUE, {
      connection,
      defaultJobOptions: {
        attempts: 3,
        backoff: { type: "exponential", delay: 2_000 },
        removeOnComplete: { age: 60 * 60 * 24, count: 1000 },
        removeOnFail: { age: 60 * 60 * 24 * 7 },
      },
    });
  }
  return cached;
}

export async function enqueueParse(job: ParseDocumentJob) {
  return parseQueue().add("parse", job, { jobId: job.documentId });
}
