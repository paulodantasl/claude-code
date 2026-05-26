import { getDb } from "./client.js";
import {
  organizations,
  users,
  memberships,
  projects,
  rfqTemplates,
  requirementTemplates,
} from "./schema.js";
import { eq, and } from "drizzle-orm";
import { TRADE_TEMPLATES, REQUIREMENT_TEMPLATES } from "./templates.js";

async function seedTemplates() {
  const db = getDb();
  let rfqInserted = 0;
  for (const tpl of TRADE_TEMPLATES) {
    const existing = await db
      .select()
      .from(rfqTemplates)
      .where(and(eq(rfqTemplates.name, tpl.name), eq(rfqTemplates.trade, tpl.trade)))
      .limit(1);
    if (existing[0]) continue;
    await db.insert(rfqTemplates).values(tpl);
    rfqInserted++;
  }
  if (rfqInserted > 0) console.log(`Seeded ${rfqInserted} RFQ template(s).`);

  let reqInserted = 0;
  for (const tpl of REQUIREMENT_TEMPLATES) {
    const existing = await db
      .select()
      .from(requirementTemplates)
      .where(eq(requirementTemplates.name, tpl.name))
      .limit(1);
    if (existing[0]) continue;
    await db.insert(requirementTemplates).values(tpl);
    reqInserted++;
  }
  if (reqInserted > 0) console.log(`Seeded ${reqInserted} requirement template(s).`);
}

async function main() {
  const db = getDb();
  const email = "dev@example.test";

  await seedTemplates();

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
