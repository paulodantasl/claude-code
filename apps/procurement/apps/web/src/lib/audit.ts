import { auditEvents, type AuditEventInsert } from "@procurement/db";
import { db } from "./db.js";

export async function recordAudit(event: Omit<AuditEventInsert, "id" | "createdAt">) {
  await db.insert(auditEvents).values(event);
}
