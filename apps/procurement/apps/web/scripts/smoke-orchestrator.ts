// Direct smoke test for the procurement orchestrator: exercises the stub
// provider against a real Postgres, validating the schema, tool wiring, and
// state persistence end-to-end (without needing the Next HTTP server).
//
// Run with:
//   DATABASE_URL=... pnpm exec tsx scripts/smoke-orchestrator.ts

import { eq } from "drizzle-orm";
import {
  getDb,
  documents,
  documentChunks,
  packages as packagesTable,
  procurementRequests,
  procurementRequestMessages,
  projects,
  rfqDrafts,
  rfqTemplates,
  users,
  vendors,
  type NeedSpec,
} from "@procurement/db";
import {
  selectOrchestrator,
  type OrchestratorState,
  type OrchestratorTools,
} from "@procurement/llm";

const DATABASE_URL =
  process.env.DATABASE_URL ?? "postgres://procurement:procurement@localhost:5432/procurement";
const db = getDb(DATABASE_URL);

async function main() {
  const [user] = await db.select().from(users).limit(1);
  const [project] = await db.select().from(projects).limit(1);
  if (!user || !project) throw new Error("Seed not present — run `pnpm seed` first.");
  console.log(`Project: ${project.id} (${project.name})`);

  // Ensure a concrete spec exists (so search would work in the real path).
  const existing = await db.select().from(documents).where(eq(documents.projectId, project.id));
  if (!existing.find((d) => d.title === "Concrete Spec (smoke)")) {
    const [doc] = await db
      .insert(documents)
      .values({
        projectId: project.id,
        kind: "spec",
        title: "Concrete Spec (smoke)",
        mimeType: "application/pdf",
        sizeBytes: 1000,
        storageKey: "k-smoke",
        sha256: "smoke",
        status: "parsed",
        pageCount: 2,
      })
      .returning();
    await db.insert(documentChunks).values([
      {
        documentId: doc!.id,
        page: 1,
        chunkIndex: 0,
        text: "Slabs-on-grade: 4000 psi at 28 days, w/c <= 0.45, cement ASTM C150 Type I/II.",
      },
      {
        documentId: doc!.id,
        page: 2,
        chunkIndex: 0,
        text: "Cure all slabs for a minimum of 7 days using wet curing or curing compound per ASTM C309.",
      },
    ]);
  }

  // Ensure a vendor matching trade=concrete exists.
  const existingVendors = await db
    .select()
    .from(vendors)
    .where(eq(vendors.organizationId, project.organizationId));
  if (!existingVendors.some((v) => v.trades.includes("concrete"))) {
    await db.insert(vendors).values({
      organizationId: project.organizationId,
      name: "Acme Concrete Inc. (smoke)",
      trades: ["concrete"],
      contactEmail: "bids@acme.test",
    });
  }

  const orchestrator = selectOrchestrator({ apiKey: "", model: "stub" });
  console.log(`Orchestrator: ${orchestrator.name}`);

  // Build the request as the router would.
  const initial =
    "I need 670 cubic yards of 4000 psi cast-in-place concrete for slabs and walls, delivery in 6 weeks. Max w/c 0.45.";
  const [request] = await db
    .insert(procurementRequests)
    .values({
      projectId: project.id,
      title: "Smoke — concrete 670 CY",
      status: "intake",
      need: {
        item: null,
        quantity: null,
        unit: null,
        deadline: null,
        jurisdiction: null,
        trade: null,
        specs: [],
        notes: null,
      } satisfies NeedSpec,
      createdBy: user.id,
    })
    .returning();
  console.log(`Created request: ${request!.id}`);

  // Same heuristic as the router uses.
  function heuristic(text: string, current: NeedSpec): Partial<NeedSpec> {
    const fields: Partial<NeedSpec> = {};
    const qty = text.match(
      /(\d[\d,]*(?:\.\d+)?)\s*(cubic\s+yards?|cy|tons?|sf|lf|each|ea|ls)/i,
    );
    if (qty && current.quantity == null) {
      fields.quantity = Number(qty[1]!.replace(/,/g, ""));
      const u = qty[2]!.toLowerCase();
      fields.unit = u.startsWith("cubic") || u === "cy" ? "CY" : u.toUpperCase();
    }
    if (!current.trade && /concrete|slab|cast.in.place/i.test(text)) fields.trade = "concrete";
    if (!current.item) fields.item = text.slice(0, 100);
    const psi = text.match(/(\d{3,5})\s*psi/i);
    if (psi) fields.specs = Array.from(new Set([...current.specs, `${psi[1]} psi`]));
    const wks = text.match(/in\s+(\d+)\s+weeks?/i);
    if (wks && !current.deadline) fields.deadline = `+${wks[1]}w`;
    return fields;
  }

  let workingNeed: NeedSpec = request!.need;
  let workingPackageId: string | null = null;
  let workingRfqDraftId: string | null = null;

  const tools: OrchestratorTools = {
    extract_need: async ({ text }) => heuristic(text, workingNeed),
    update_need: async ({ fields }) => {
      workingNeed = { ...workingNeed, ...fields };
      return workingNeed;
    },
    search_project_docs: async () => ({ hits: [] }),
    list_rfq_templates: async ({ trade }) => {
      const rows = await db.select().from(rfqTemplates);
      const filtered = trade ? rows.filter((r) => r.trade === trade) : rows;
      return filtered.map((r) => ({
        id: r.id,
        name: r.name,
        trade: r.trade,
        division: r.division,
      }));
    },
    create_package_and_rfq_draft: async ({ title, templateId }) => {
      const [tpl] = await db
        .select()
        .from(rfqTemplates)
        .where(eq(rfqTemplates.id, templateId))
        .limit(1);
      const [pkg] = await db
        .insert(packagesTable)
        .values({ projectId: project.id, kind: "sourcing", name: title })
        .returning();
      const [draft] = await db
        .insert(rfqDrafts)
        .values({
          projectId: project.id,
          packageId: pkg!.id,
          templateId: tpl!.id,
          title,
          currentSections: tpl!.sections.map((s) => ({
            id: s.id,
            title: s.title,
            body: "",
            citations: [],
            generatedAt: null,
            editedAt: null,
          })),
          createdBy: user.id,
        })
        .returning();
      workingPackageId = pkg!.id;
      workingRfqDraftId = draft!.id;
      return {
        packageId: pkg!.id,
        rfqDraftId: draft!.id,
        sections: tpl!.sections.map((s) => ({ id: s.id, title: s.title })),
      };
    },
    generate_rfq_section: async ({ sectionId }) => ({
      sectionId,
      citationCount: 0,
      bodyPreview: "(smoke)",
    }),
    list_vendors: async ({ trade }) => {
      const rows = await db
        .select()
        .from(vendors)
        .where(eq(vendors.organizationId, project.organizationId));
      const filtered = trade ? rows.filter((v) => v.trades.includes(trade)) : rows;
      return filtered.map((v) => ({
        id: v.id,
        name: v.name,
        trades: v.trades,
        contactEmail: v.contactEmail,
      }));
    },
    list_bids: async () => [],
    create_comparison: async () => ({
      comparisonRunId: "",
      rowCount: 0,
      flagCount: 0,
      recommendedVendorId: null,
      recommendedVendorName: null,
      recommendationReason: "",
    }),
    set_status: async ({ status }) => {
      await db
        .update(procurementRequests)
        .set({ status: status as OrchestratorState["status"], updatedAt: new Date() })
        .where(eq(procurementRequests.id, request!.id));
    },
    set_recommendation: async ({ text }) => {
      await db
        .update(procurementRequests)
        .set({ recommendation: text, updatedAt: new Date() })
        .where(eq(procurementRequests.id, request!.id));
    },
  };

  // TURN 1
  const state: OrchestratorState = {
    need: workingNeed,
    status: "intake",
    packageId: null,
    rfqDraftId: null,
    comparisonRunId: null,
    recommendation: null,
  };
  const turn = await orchestrator.runTurn({
    state,
    history: [],
    userMessage: initial,
    tools,
  });
  console.log("\n=== TURN 1 ===");
  console.log("reply:", turn.reply);
  console.log("actions:");
  for (const a of turn.actions) console.log(`  - ${a.tool}: ${a.summary}`);
  console.log("artifacts:", turn.artifacts.map((a) => `${a.kind}=${a.label}`).join("; "));

  // Persist the agent message + state updates as the real router would.
  const updates: Record<string, unknown> = { updatedAt: new Date(), need: workingNeed };
  if (workingPackageId) updates.packageId = workingPackageId;
  if (workingRfqDraftId) updates.rfqDraftId = workingRfqDraftId;
  if (turn.stateUpdates.status) updates.status = turn.stateUpdates.status;
  await db.update(procurementRequests).set(updates).where(eq(procurementRequests.id, request!.id));
  await db.insert(procurementRequestMessages).values({
    requestId: request!.id,
    role: "agent",
    content: turn.reply,
    artifacts: turn.artifacts,
    actions: turn.actions,
  });

  const final = (
    await db.select().from(procurementRequests).where(eq(procurementRequests.id, request!.id)).limit(1)
  )[0]!;
  console.log("\n=== DB STATE AFTER TURN 1 ===");
  console.log("status:", final.status);
  console.log("need:", JSON.stringify(final.need));
  console.log("packageId:", final.packageId);
  console.log("rfqDraftId:", final.rfqDraftId);
  const messages = await db
    .select()
    .from(procurementRequestMessages)
    .where(eq(procurementRequestMessages.requestId, request!.id));
  console.log("messages:", messages.length);

  // Assertions
  const errors: string[] = [];
  if (final.status !== "awaiting_bids") errors.push(`status: expected awaiting_bids, got ${final.status}`);
  if (final.need.quantity !== 670) errors.push(`qty: expected 670, got ${final.need.quantity}`);
  if (final.need.unit !== "CY") errors.push(`unit: expected CY, got ${final.need.unit}`);
  if (final.need.trade !== "concrete") errors.push(`trade: expected concrete, got ${final.need.trade}`);
  if (!final.packageId) errors.push("expected packageId set");
  if (!final.rfqDraftId) errors.push("expected rfqDraftId set");
  if (errors.length > 0) {
    console.error("\n❌ ASSERTIONS FAILED:");
    for (const e of errors) console.error(`  - ${e}`);
    process.exit(1);
  }
  console.log("\n✅ ALL ASSERTIONS PASSED");

  // Cleanup
  if (workingPackageId) {
    await db.delete(rfqDrafts).where(eq(rfqDrafts.id, workingRfqDraftId!));
    await db.delete(packagesTable).where(eq(packagesTable.id, workingPackageId));
  }
  await db.delete(procurementRequests).where(eq(procurementRequests.id, request!.id));
  await db.delete(documents).where(eq(documents.title, "Concrete Spec (smoke)"));
  await db
    .delete(vendors)
    .where(eq(vendors.name, "Acme Concrete Inc. (smoke)"));
  console.log("(cleaned up smoke data)");
  process.exit(0);
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
