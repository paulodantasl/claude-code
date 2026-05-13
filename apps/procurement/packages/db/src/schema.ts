import {
  pgTable,
  pgEnum,
  uuid,
  text,
  varchar,
  timestamp,
  integer,
  jsonb,
  boolean,
  primaryKey,
  index,
  uniqueIndex,
} from "drizzle-orm/pg-core";
import { sql } from "drizzle-orm";

export const userRoleEnum = pgEnum("user_role", [
  "admin",
  "procurement",
  "pm_read_only",
]);

export const documentStatusEnum = pgEnum("document_status", [
  "uploaded",
  "scanning",
  "parsing",
  "parsed",
  "failed",
]);

export const documentKindEnum = pgEnum("document_kind", [
  "spec",
  "addendum",
  "drawing_index",
  "bid",
  "submittal",
  "sds",
  "warranty",
  "coi",
  "lien_waiver",
  "other",
]);

export const packageKindEnum = pgEnum("package_kind", ["sourcing", "compliance"]);

const now = sql`now()`;

export const organizations = pgTable("organizations", {
  id: uuid("id").defaultRandom().primaryKey(),
  name: text("name").notNull(),
  createdAt: timestamp("created_at", { withTimezone: true }).default(now).notNull(),
});

export const users = pgTable(
  "users",
  {
    id: uuid("id").defaultRandom().primaryKey(),
    email: varchar("email", { length: 320 }).notNull(),
    name: text("name"),
    createdAt: timestamp("created_at", { withTimezone: true }).default(now).notNull(),
  },
  (t) => ({
    emailIdx: uniqueIndex("users_email_idx").on(t.email),
  }),
);

export const memberships = pgTable(
  "memberships",
  {
    userId: uuid("user_id")
      .notNull()
      .references(() => users.id, { onDelete: "cascade" }),
    organizationId: uuid("organization_id")
      .notNull()
      .references(() => organizations.id, { onDelete: "cascade" }),
    role: userRoleEnum("role").notNull().default("procurement"),
    createdAt: timestamp("created_at", { withTimezone: true }).default(now).notNull(),
  },
  (t) => ({
    pk: primaryKey({ columns: [t.userId, t.organizationId] }),
    orgIdx: index("memberships_org_idx").on(t.organizationId),
  }),
);

export const magicLinkTokens = pgTable(
  "magic_link_tokens",
  {
    tokenHash: varchar("token_hash", { length: 128 }).primaryKey(),
    email: varchar("email", { length: 320 }).notNull(),
    expiresAt: timestamp("expires_at", { withTimezone: true }).notNull(),
    consumedAt: timestamp("consumed_at", { withTimezone: true }),
    createdAt: timestamp("created_at", { withTimezone: true }).default(now).notNull(),
  },
  (t) => ({
    emailIdx: index("magic_link_email_idx").on(t.email),
  }),
);

export const sessions = pgTable(
  "sessions",
  {
    id: uuid("id").defaultRandom().primaryKey(),
    userId: uuid("user_id")
      .notNull()
      .references(() => users.id, { onDelete: "cascade" }),
    tokenHash: varchar("token_hash", { length: 128 }).notNull(),
    expiresAt: timestamp("expires_at", { withTimezone: true }).notNull(),
    createdAt: timestamp("created_at", { withTimezone: true }).default(now).notNull(),
  },
  (t) => ({
    tokenIdx: uniqueIndex("sessions_token_idx").on(t.tokenHash),
    userIdx: index("sessions_user_idx").on(t.userId),
  }),
);

export const projects = pgTable(
  "projects",
  {
    id: uuid("id").defaultRandom().primaryKey(),
    organizationId: uuid("organization_id")
      .notNull()
      .references(() => organizations.id, { onDelete: "cascade" }),
    name: text("name").notNull(),
    jurisdiction: text("jurisdiction"),
    notes: text("notes"),
    createdBy: uuid("created_by").references(() => users.id, { onDelete: "set null" }),
    createdAt: timestamp("created_at", { withTimezone: true }).default(now).notNull(),
  },
  (t) => ({
    orgIdx: index("projects_org_idx").on(t.organizationId),
  }),
);

export const packages = pgTable(
  "packages",
  {
    id: uuid("id").defaultRandom().primaryKey(),
    projectId: uuid("project_id")
      .notNull()
      .references(() => projects.id, { onDelete: "cascade" }),
    kind: packageKindEnum("kind").notNull(),
    name: text("name").notNull(),
    scopeNotes: text("scope_notes"),
    bidDueAt: timestamp("bid_due_at", { withTimezone: true }),
    createdAt: timestamp("created_at", { withTimezone: true }).default(now).notNull(),
  },
  (t) => ({
    projectIdx: index("packages_project_idx").on(t.projectId),
  }),
);

export const vendors = pgTable(
  "vendors",
  {
    id: uuid("id").defaultRandom().primaryKey(),
    organizationId: uuid("organization_id")
      .notNull()
      .references(() => organizations.id, { onDelete: "cascade" }),
    name: text("name").notNull(),
    contactName: text("contact_name"),
    contactEmail: varchar("contact_email", { length: 320 }),
    trades: jsonb("trades").$type<string[]>().default(sql`'[]'::jsonb`).notNull(),
    createdAt: timestamp("created_at", { withTimezone: true }).default(now).notNull(),
  },
  (t) => ({
    orgIdx: index("vendors_org_idx").on(t.organizationId),
  }),
);

export const documents = pgTable(
  "documents",
  {
    id: uuid("id").defaultRandom().primaryKey(),
    projectId: uuid("project_id")
      .notNull()
      .references(() => projects.id, { onDelete: "cascade" }),
    packageId: uuid("package_id").references(() => packages.id, { onDelete: "set null" }),
    vendorId: uuid("vendor_id").references(() => vendors.id, { onDelete: "set null" }),
    kind: documentKindEnum("kind").notNull().default("other"),
    title: text("title").notNull(),
    mimeType: varchar("mime_type", { length: 128 }).notNull(),
    sizeBytes: integer("size_bytes").notNull(),
    storageKey: text("storage_key").notNull(),
    sha256: varchar("sha256", { length: 64 }).notNull(),
    status: documentStatusEnum("status").notNull().default("uploaded"),
    pageCount: integer("page_count"),
    parseError: text("parse_error"),
    uploadedBy: uuid("uploaded_by").references(() => users.id, { onDelete: "set null" }),
    uploadedAt: timestamp("uploaded_at", { withTimezone: true }).default(now).notNull(),
    parsedAt: timestamp("parsed_at", { withTimezone: true }),
  },
  (t) => ({
    projectIdx: index("documents_project_idx").on(t.projectId),
    statusIdx: index("documents_status_idx").on(t.status),
    shaIdx: index("documents_sha_idx").on(t.sha256),
  }),
);

export const documentChunks = pgTable(
  "document_chunks",
  {
    id: uuid("id").defaultRandom().primaryKey(),
    documentId: uuid("document_id")
      .notNull()
      .references(() => documents.id, { onDelete: "cascade" }),
    page: integer("page").notNull(),
    chunkIndex: integer("chunk_index").notNull(),
    text: text("text").notNull(),
    tokenCount: integer("token_count"),
    // bbox stored as [x0, y0, x1, y1] in PDF point space, optional
    bbox: jsonb("bbox").$type<[number, number, number, number] | null>(),
    createdAt: timestamp("created_at", { withTimezone: true }).default(now).notNull(),
  },
  (t) => ({
    docIdx: index("chunks_doc_idx").on(t.documentId),
    pageIdx: index("chunks_doc_page_idx").on(t.documentId, t.page),
    // tsvector for full-text search; populated via trigger or manual update
    fts: index("chunks_fts_idx")
      .using("gin", sql`to_tsvector('english', ${t.text})`),
  }),
);

export const auditEvents = pgTable(
  "audit_events",
  {
    id: uuid("id").defaultRandom().primaryKey(),
    organizationId: uuid("organization_id").references(() => organizations.id, {
      onDelete: "cascade",
    }),
    projectId: uuid("project_id").references(() => projects.id, { onDelete: "cascade" }),
    userId: uuid("user_id").references(() => users.id, { onDelete: "set null" }),
    action: varchar("action", { length: 64 }).notNull(),
    targetType: varchar("target_type", { length: 64 }),
    targetId: uuid("target_id"),
    metadata: jsonb("metadata").$type<Record<string, unknown>>(),
    createdAt: timestamp("created_at", { withTimezone: true }).default(now).notNull(),
  },
  (t) => ({
    orgIdx: index("audit_org_idx").on(t.organizationId, t.createdAt),
    projectIdx: index("audit_project_idx").on(t.projectId, t.createdAt),
    actionIdx: index("audit_action_idx").on(t.action),
  }),
);

export const chatThreads = pgTable(
  "chat_threads",
  {
    id: uuid("id").defaultRandom().primaryKey(),
    projectId: uuid("project_id")
      .notNull()
      .references(() => projects.id, { onDelete: "cascade" }),
    createdBy: uuid("created_by").references(() => users.id, { onDelete: "set null" }),
    title: text("title").notNull().default("Untitled"),
    createdAt: timestamp("created_at", { withTimezone: true }).default(now).notNull(),
    updatedAt: timestamp("updated_at", { withTimezone: true }).default(now).notNull(),
  },
  (t) => ({
    projectIdx: index("chat_threads_project_idx").on(t.projectId),
  }),
);

export const chatMessages = pgTable(
  "chat_messages",
  {
    id: uuid("id").defaultRandom().primaryKey(),
    threadId: uuid("thread_id")
      .notNull()
      .references(() => chatThreads.id, { onDelete: "cascade" }),
    role: varchar("role", { length: 16 }).notNull(),
    content: text("content").notNull(),
    // Citations: [{ documentId, page, chunkId, snippet }]
    citations: jsonb("citations")
      .$type<
        Array<{
          documentId: string;
          page: number;
          chunkId: string;
          snippet: string;
        }>
      >()
      .default(sql`'[]'::jsonb`)
      .notNull(),
    // Tool traces for audit/replay (model output, tool inputs, tool outputs)
    trace: jsonb("trace").$type<Record<string, unknown>>(),
    createdAt: timestamp("created_at", { withTimezone: true }).default(now).notNull(),
  },
  (t) => ({
    threadIdx: index("chat_messages_thread_idx").on(t.threadId, t.createdAt),
  }),
);

export const documentScans = pgTable(
  "document_scans",
  {
    documentId: uuid("document_id")
      .primaryKey()
      .references(() => documents.id, { onDelete: "cascade" }),
    clean: boolean("clean").notNull().default(true),
    scanner: text("scanner").notNull().default("stub"),
    scannedAt: timestamp("scanned_at", { withTimezone: true }).default(now).notNull(),
  },
);

export type Organization = typeof organizations.$inferSelect;
export type User = typeof users.$inferSelect;
export type Project = typeof projects.$inferSelect;
export type ProjectInsert = typeof projects.$inferInsert;
export type Package = typeof packages.$inferSelect;
export type Document = typeof documents.$inferSelect;
export type DocumentInsert = typeof documents.$inferInsert;
export type DocumentChunk = typeof documentChunks.$inferSelect;
export type DocumentChunkInsert = typeof documentChunks.$inferInsert;
export type ChatMessage = typeof chatMessages.$inferSelect;
export type ChatThread = typeof chatThreads.$inferSelect;
export type AuditEvent = typeof auditEvents.$inferSelect;
export type AuditEventInsert = typeof auditEvents.$inferInsert;
