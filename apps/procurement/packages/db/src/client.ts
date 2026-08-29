import { drizzle } from "drizzle-orm/postgres-js";
import postgres from "postgres";
import * as schema from "./schema.js";

let cached: ReturnType<typeof drizzle<typeof schema>> | null = null;

export function getDb(connectionString: string = process.env.DATABASE_URL ?? "") {
  if (!connectionString) {
    throw new Error("DATABASE_URL is required");
  }
  if (cached) return cached;
  const client = postgres(connectionString, { max: 10, prepare: false });
  cached = drizzle(client, { schema });
  return cached;
}

export type Db = ReturnType<typeof getDb>;
