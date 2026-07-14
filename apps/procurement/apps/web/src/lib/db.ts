import { getDb } from "@procurement/db";
import { env } from "./env";

export const db = getDb(env.DATABASE_URL);
