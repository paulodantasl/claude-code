"use client";
import Link from "next/link";

interface Citation {
  documentId: string;
  page: number;
  chunkId: string;
  snippet: string;
}

export function CitationChip({
  projectId,
  citation,
  compact = false,
}: {
  projectId: string;
  citation: Citation;
  compact?: boolean;
}) {
  return (
    <Link
      href={`/projects/${projectId}/documents/${citation.documentId}?page=${citation.page}`}
      title={citation.snippet}
      className="prose-citation"
    >
      {compact ? "" : "doc "}p{citation.page}
    </Link>
  );
}
