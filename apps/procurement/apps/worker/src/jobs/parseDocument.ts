import { eq } from "drizzle-orm";
import { getDb, documents, documentChunks, auditEvents } from "@procurement/db";
import type { ParseDocumentJob } from "@procurement/shared";
import { loadEnv } from "@procurement/shared/env";
import { getObjectBytes } from "../lib/storage.js";
import { parsePdf } from "../lib/pdf.js";
import { parseXlsx } from "../lib/xlsx.js";
import { chunkPages } from "../lib/chunker.js";

const env = loadEnv();
const db = getDb(env.DATABASE_URL);

export async function runParseJob(job: ParseDocumentJob): Promise<void> {
  const [doc] = await db.select().from(documents).where(eq(documents.id, job.documentId)).limit(1);
  if (!doc) {
    console.warn(`[parse] no document found for ${job.documentId}, skipping`);
    return;
  }

  try {
    const buf = await getObjectBytes(job.storageKey);
    const parsed = await parseFor(job.mimeType, buf);
    const chunks = chunkPages(parsed.pages);

    // Replace any prior chunks for idempotency.
    await db.delete(documentChunks).where(eq(documentChunks.documentId, doc.id));
    if (chunks.length > 0) {
      await db.insert(documentChunks).values(
        chunks.map((c) => ({
          documentId: doc.id,
          page: c.page,
          chunkIndex: c.index,
          text: c.text,
          tokenCount: c.tokenCount,
        })),
      );
    }
    await db
      .update(documents)
      .set({
        status: "parsed",
        pageCount: parsed.pageCount,
        parseError: null,
        parsedAt: new Date(),
      })
      .where(eq(documents.id, doc.id));
    await db.insert(auditEvents).values({
      organizationId: null,
      projectId: doc.projectId,
      action: "document.parsed",
      targetType: "document",
      targetId: doc.id,
      metadata: {
        pageCount: parsed.pageCount,
        chunkCount: chunks.length,
        mimeType: job.mimeType,
      },
    });
    console.log(`[parse] ${doc.id} parsed: ${parsed.pageCount} pages, ${chunks.length} chunks`);
  } catch (err) {
    const message = err instanceof Error ? err.message : String(err);
    console.error(`[parse] failed for ${doc.id}: ${message}`);
    await db
      .update(documents)
      .set({ status: "failed", parseError: message })
      .where(eq(documents.id, doc.id));
    await db.insert(auditEvents).values({
      projectId: doc.projectId,
      action: "document.parse_failed",
      targetType: "document",
      targetId: doc.id,
      metadata: { error: message },
    });
    throw err;
  }
}

async function parseFor(mimeType: string, buf: Buffer) {
  if (mimeType === "application/pdf") return parsePdf(buf);
  if (
    mimeType === "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" ||
    mimeType === "application/vnd.ms-excel"
  ) {
    return parseXlsx(buf);
  }
  throw new Error(`Unsupported MIME type: ${mimeType}`);
}
