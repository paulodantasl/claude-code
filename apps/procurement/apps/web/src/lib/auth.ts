import { cookies } from "next/headers";
import { and, eq, gt } from "drizzle-orm";
import {
  magicLinkTokens,
  memberships,
  organizations,
  sessions,
  users,
} from "@procurement/db";
import { db } from "./db.js";
import { randomToken, sha256 } from "./crypto.js";
import { env } from "./env.js";

const SESSION_COOKIE = "procurement_session";
const SESSION_TTL_MS = 1000 * 60 * 60 * 24 * 14; // 14 days
const MAGIC_TTL_MS = 1000 * 60 * 30; // 30 min

export async function createMagicLink(email: string): Promise<string> {
  const token = randomToken(32);
  const tokenHash = sha256(token);
  const expiresAt = new Date(Date.now() + MAGIC_TTL_MS);
  await db.insert(magicLinkTokens).values({
    tokenHash,
    email: email.toLowerCase().trim(),
    expiresAt,
  });
  const url = new URL("/auth/verify", env.NEXTAUTH_URL);
  url.searchParams.set("token", token);
  return url.toString();
}

export async function consumeMagicLink(token: string): Promise<{ userId: string }> {
  const tokenHash = sha256(token);
  const rows = await db
    .select()
    .from(magicLinkTokens)
    .where(
      and(eq(magicLinkTokens.tokenHash, tokenHash), gt(magicLinkTokens.expiresAt, new Date())),
    )
    .limit(1);
  const record = rows[0];
  if (!record || record.consumedAt) {
    throw new Error("This magic link is invalid or already used.");
  }
  await db
    .update(magicLinkTokens)
    .set({ consumedAt: new Date() })
    .where(eq(magicLinkTokens.tokenHash, tokenHash));

  // Find or create user. First-time users get a personal organization so the
  // single-tenant flow works without an invite UI in Phase 0.
  let user = (
    await db.select().from(users).where(eq(users.email, record.email)).limit(1)
  )[0];
  if (!user) {
    [user] = await db
      .insert(users)
      .values({ email: record.email })
      .returning();
    const [org] = await db
      .insert(organizations)
      .values({ name: `${record.email.split("@")[0]}'s workspace` })
      .returning();
    await db.insert(memberships).values({
      userId: user.id,
      organizationId: org.id,
      role: "admin",
    });
  }
  return { userId: user.id };
}

export async function startSession(userId: string): Promise<void> {
  const sessionToken = randomToken(32);
  const tokenHash = sha256(sessionToken);
  const expiresAt = new Date(Date.now() + SESSION_TTL_MS);
  await db.insert(sessions).values({ userId, tokenHash, expiresAt });
  cookies().set(SESSION_COOKIE, sessionToken, {
    httpOnly: true,
    secure: env.NEXTAUTH_URL.startsWith("https://"),
    sameSite: "lax",
    path: "/",
    expires: expiresAt,
  });
}

export async function endSession(): Promise<void> {
  const cookie = cookies().get(SESSION_COOKIE);
  if (cookie) {
    const tokenHash = sha256(cookie.value);
    await db.delete(sessions).where(eq(sessions.tokenHash, tokenHash));
  }
  cookies().delete(SESSION_COOKIE);
}

export interface SessionContext {
  userId: string;
  email: string;
  organizations: Array<{ id: string; name: string; role: "admin" | "procurement" | "pm_read_only" }>;
}

export async function getSession(): Promise<SessionContext | null> {
  const cookie = cookies().get(SESSION_COOKIE);
  if (!cookie) return null;
  const tokenHash = sha256(cookie.value);
  const sessionRows = await db
    .select({
      user: users,
      session: sessions,
    })
    .from(sessions)
    .innerJoin(users, eq(sessions.userId, users.id))
    .where(and(eq(sessions.tokenHash, tokenHash), gt(sessions.expiresAt, new Date())))
    .limit(1);
  const row = sessionRows[0];
  if (!row) return null;
  const orgRows = await db
    .select({
      id: organizations.id,
      name: organizations.name,
      role: memberships.role,
    })
    .from(memberships)
    .innerJoin(organizations, eq(memberships.organizationId, organizations.id))
    .where(eq(memberships.userId, row.user.id));
  return {
    userId: row.user.id,
    email: row.user.email,
    organizations: orgRows,
  };
}
