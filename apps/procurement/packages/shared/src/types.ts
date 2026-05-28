import { z } from "zod";

export const citationSchema = z.object({
  documentId: z.string().uuid(),
  page: z.number().int().min(1),
  chunkId: z.string().uuid(),
  snippet: z.string(),
});
export type Citation = z.infer<typeof citationSchema>;

export const parseDocumentJobSchema = z.object({
  documentId: z.string().uuid(),
  storageKey: z.string().min(1),
  mimeType: z.string().min(1),
});
export type ParseDocumentJob = z.infer<typeof parseDocumentJobSchema>;

export const PARSE_QUEUE = "parse-document" as const;

export const searchQuerySchema = z.object({
  projectId: z.string().uuid(),
  query: z.string().min(1).max(500),
  limit: z.number().int().min(1).max(20).default(8),
});
export type SearchQuery = z.infer<typeof searchQuerySchema>;

export const searchHitSchema = z.object({
  documentId: z.string().uuid(),
  documentTitle: z.string(),
  page: z.number().int().min(1),
  chunkId: z.string().uuid(),
  snippet: z.string(),
  score: z.number(),
});
export type SearchHit = z.infer<typeof searchHitSchema>;

// Roles
export const ROLE_PERMISSIONS = {
  admin: { canWrite: true, canManageMembers: true },
  procurement: { canWrite: true, canManageMembers: false },
  pm_read_only: { canWrite: false, canManageMembers: false },
} as const;
export type Role = keyof typeof ROLE_PERMISSIONS;

// Procurement-request need shape — used by db (for jsonb column type) and llm
// (orchestrator input/output). Keeping it in shared keeps llm independent of db.
export interface NeedSpec {
  item: string | null;
  quantity: number | null;
  unit: string | null;
  deadline: string | null;
  jurisdiction: string | null;
  trade: string | null;
  specs: string[];
  notes: string | null;
}
