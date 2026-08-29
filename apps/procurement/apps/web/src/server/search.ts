import { sql } from "drizzle-orm";
import { documents, documentChunks } from "@procurement/db";
import { db } from "@/lib/db";
import type { SearchHit } from "@procurement/shared";

// Postgres full-text search over chunk text, scoped to a project. The query
// is fed through `plainto_tsquery` so users (and the LLM) don't need to know
// tsquery syntax.
export async function searchProjectDocs(
  projectId: string,
  query: string,
  limit = 8,
): Promise<SearchHit[]> {
  const rows = await db
    .select({
      documentId: documentChunks.documentId,
      documentTitle: documents.title,
      page: documentChunks.page,
      chunkId: documentChunks.id,
      snippet: sql<string>`ts_headline('english', ${documentChunks.text}, plainto_tsquery('english', ${query}), 'StartSel=<mark>,StopSel=</mark>,MaxFragments=2,MaxWords=35,MinWords=15')`,
      score: sql<number>`ts_rank(to_tsvector('english', ${documentChunks.text}), plainto_tsquery('english', ${query}))`,
    })
    .from(documentChunks)
    .innerJoin(documents, sql`${documents.id} = ${documentChunks.documentId}`)
    .where(
      sql`${documents.projectId} = ${projectId} AND to_tsvector('english', ${documentChunks.text}) @@ plainto_tsquery('english', ${query})`,
    )
    .orderBy(sql`score desc`)
    .limit(limit);

  return rows.map((r) => ({
    documentId: r.documentId,
    documentTitle: r.documentTitle,
    page: r.page,
    chunkId: r.chunkId,
    // Strip <mark> tags for now; UI can highlight if it wants.
    snippet: r.snippet.replace(/<\/?mark>/g, ""),
    score: Number(r.score) || 0,
  }));
}

export async function getPageText(
  projectId: string,
  documentId: string,
  page: number,
): Promise<{ documentTitle: string; page: number; text: string }> {
  const rows = await db
    .select({
      title: documents.title,
      text: documentChunks.text,
    })
    .from(documentChunks)
    .innerJoin(documents, sql`${documents.id} = ${documentChunks.documentId}`)
    .where(
      sql`${documents.projectId} = ${projectId} AND ${documentChunks.documentId} = ${documentId} AND ${documentChunks.page} = ${page}`,
    )
    .orderBy(documentChunks.chunkIndex);
  if (rows.length === 0) {
    throw new Error(`No parsed text for document ${documentId} page ${page}.`);
  }
  return {
    documentTitle: rows[0]!.title,
    page,
    text: rows.map((r) => r.text).join("\n\n"),
  };
}
