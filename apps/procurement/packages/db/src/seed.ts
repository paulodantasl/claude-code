import { getDb } from "./client.js";
import { organizations, users, memberships, projects } from "./schema.js";
import { eq } from "drizzle-orm";

async function main() {
  const db = getDb();
  const email = "dev@example.test";

  const [existingUser] = await db.select().from(users).where(eq(users.email, email));
  if (existingUser) {
    console.log(`Seed user already exists: ${email}`);
    return;
  }

  const [org] = await db
    .insert(organizations)
    .values({ name: "Demo GC" })
    .returning();
  const [user] = await db
    .insert(users)
    .values({ email, name: "Dev User" })
    .returning();
  await db.insert(memberships).values({
    userId: user.id,
    organizationId: org.id,
    role: "admin",
  });
  const [project] = await db
    .insert(projects)
    .values({
      organizationId: org.id,
      name: "1234 Market Street – Office Fit-out",
      jurisdiction: "San Francisco, CA",
      notes: "Demo project for Phase 0 vertical slice.",
      createdBy: user.id,
    })
    .returning();

  console.log("Seeded:");
  console.log(`  Org:     ${org.id} (${org.name})`);
  console.log(`  User:    ${user.id} (${user.email})`);
  console.log(`  Project: ${project.id} (${project.name})`);
  console.log("Sign in at http://localhost:3000 with email:", email);
  process.exit(0);
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
