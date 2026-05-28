// Full end-to-end smoke: state a need → agent intakes → creates RFQ →
// register two bids → extract → second turn → agent compares + recommends.

import { eq } from "drizzle-orm";
import {
  bids as bidsTable,
  comparisonRuns,
  documents,
  documentChunks,
  getDb,
  packages as packagesTable,
  procurementRequests,
  procurementRequestMessages,
  projects,
  rfqDrafts,
  rfqTemplates,
  users,
  vendors,
  type BidLineItem,
  type NeedSpec,
} from "@procurement/db";
import {
  selectOrchestrator,
  type OrchestratorState,
  type OrchestratorTools,
} from "@procurement/llm";
import { buildComparisonMatrix } from "../src/server/comparison-builder";

const DATABASE_URL =
  process.env.DATABASE_URL ??
  "postgres://procurement:procurement@localhost:5432/procurement";
const db = getDb(DATABASE_URL);

async function main() {
  const [user] = await db.select().from(users).limit(1);
  const [project] = await db.select().from(projects).limit(1);
  if (!user || !project) throw new Error("Seed not present");
  console.log(`Project: ${project.name}`);

  // --- Set up: parsed spec + two vendors + two parsed bid docs ---
  const ensureDoc = async (
    title: string,
    page1: string,
    page2 = "",
  ): Promise<string> => {
    const existing = (
      await db
        .select()
        .from(documents)
        .where(eq(documents.title, title))
        .limit(1)
    )[0];
    if (existing) return existing.id;
    const [d] = await db
      .insert(documents)
      .values({
        projectId: project.id,
        kind: "spec",
        title,
        mimeType: "application/pdf",
        sizeBytes: 1000,
        storageKey: `smoke/${title}`,
        sha256: `sha-${title}`,
        status: "parsed",
        pageCount: page2 ? 2 : 1,
      })
      .returning();
    const chunks = [
      { documentId: d!.id, page: 1, chunkIndex: 0, text: page1 },
    ];
    if (page2) chunks.push({ documentId: d!.id, page: 2, chunkIndex: 0, text: page2 });
    await db.insert(documentChunks).values(chunks);
    return d!.id;
  };
  await ensureDoc(
    "Concrete Spec (full-smoke)",
    "Slabs-on-grade: 4000 psi at 28 days, w/c <= 0.45.",
    "Cure all slabs for a minimum of 7 days per ASTM C309.",
  );

  const ensureVendor = async (name: string, contactEmail: string): Promise<string> => {
    const existing = (
      await db
        .select()
        .from(vendors)
        .where(eq(vendors.name, name))
        .limit(1)
    )[0];
    if (existing) return existing.id;
    const [v] = await db
      .insert(vendors)
      .values({
        organizationId: project.organizationId,
        name,
        trades: ["concrete"],
        contactEmail,
      })
      .returning();
    return v!.id;
  };
  const vendorAId = await ensureVendor("Acme Concrete Inc. (full-smoke)", "bids@acme.test");
  const vendorBId = await ensureVendor("Bayview Concrete Co. (full-smoke)", "bids@bayview.test");

  const bidDocA = await ensureDoc(
    "Bid Acme (full-smoke)",
    "Acme Concrete Inc. Bid. Footings 4000 psi @ $195/CY. Slabs $175/CY. Walls $215/CY.",
  );
  const bidDocB = await ensureDoc(
    "Bid Bayview (full-smoke)",
    "Bayview Concrete Co. Bid. Footings 4000 psi @ $210/CY. Slabs $168/CY. Walls $235/CY.",
  );

  // --- Create the request ---
  const orchestrator = selectOrchestrator({ apiKey: "", model: "stub" });
  const initial =
    "I need 670 cubic yards of 4000 psi cast-in-place concrete for slabs and walls, delivery in 6 weeks.";
  const [request] = await db
    .insert(procurementRequests)
    .values({
      projectId: project.id,
      title: "Full smoke — concrete 670 CY",
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
  if (!request) throw new Error("create request failed");

  // Heuristic extractor matching the router's
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
    if (!current.trade && /concrete|slab|cast.in.place/i.test(text))
      fields.trade = "concrete";
    if (!current.item) fields.item = text.slice(0, 100);
    const psi = text.match(/(\d{3,5})\s*psi/i);
    if (psi) fields.specs = [...new Set([...current.specs, `${psi[1]} psi`])];
    const wks = text.match(/in\s+(\d+)\s+weeks?/i);
    if (wks && !current.deadline) fields.deadline = `+${wks[1]}w`;
    return fields;
  }

  let workingNeed: NeedSpec = request.need;
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
    list_bids: async () => {
      if (!workingPackageId) return [];
      const rows = await db
        .select({ bid: bidsTable, vendor: vendors, doc: documents })
        .from(bidsTable)
        .innerJoin(vendors, eq(vendors.id, bidsTable.vendorId))
        .innerJoin(documents, eq(documents.id, bidsTable.documentId))
        .where(eq(bidsTable.packageId, workingPackageId));
      return rows.map((r) => ({
        bidId: r.bid.id,
        vendorName: r.vendor.name,
        documentTitle: r.doc.title,
        extracted: r.bid.extractedAt != null,
        baseTotalCents: r.bid.baseTotal,
        leadTimeWeeks: r.bid.leadTimeWeeks,
      }));
    },
    create_comparison: async ({ title }) => {
      if (!workingPackageId) throw new Error("no package");
      const rows = await db
        .select({ bid: bidsTable, vendor: vendors })
        .from(bidsTable)
        .innerJoin(vendors, eq(vendors.id, bidsTable.vendorId))
        .where(eq(bidsTable.packageId, workingPackageId));
      const ext = rows.filter((r) => r.bid.extractedAt && r.bid.lineItems.length > 0);
      const matrix = buildComparisonMatrix({
        bids: ext.map((r) => ({ ...r.bid, vendor: r.vendor })),
      });
      const ranking = matrix.vendors
        .map((v) => ({
          vendorId: v.id,
          name: v.name,
          baseCents: matrix.totals[v.id]?.baseCents ?? null,
          leadTime: matrix.totals[v.id]?.leadTimeWeeks ?? null,
        }))
        .filter((r) => r.baseCents != null)
        .sort((a, b) => (a.baseCents ?? 0) - (b.baseCents ?? 0));
      const winner = ranking[0];
      const [run] = await db
        .insert(comparisonRuns)
        .values({
          projectId: project.id,
          packageId: workingPackageId,
          title,
          bidIds: ext.map((r) => r.bid.id),
          matrix,
          assumptions: ["full-smoke"],
          createdBy: user.id,
        })
        .returning();
      const winBase = winner?.baseCents ? `$${(winner.baseCents / 100).toLocaleString()}` : "—";
      const reason = winner
        ? `${winner.name} has lowest base bid at ${winBase}.`
        : "no usable base totals";
      return {
        comparisonRunId: run!.id,
        rowCount: matrix.rows.length,
        flagCount: matrix.flags.length,
        recommendedVendorId: winner?.vendorId ?? null,
        recommendedVendorName: winner?.name ?? null,
        recommendationReason: reason,
      };
    },
    set_status: async ({ status }) => {
      await db
        .update(procurementRequests)
        .set({ status: status as OrchestratorState["status"], updatedAt: new Date() })
        .where(eq(procurementRequests.id, request.id));
    },
    set_recommendation: async ({ text }) => {
      await db
        .update(procurementRequests)
        .set({ recommendation: text, updatedAt: new Date() })
        .where(eq(procurementRequests.id, request.id));
    },
  };

  // ============== TURN 1 — intake → RFQ ready ==============
  const turn1 = await orchestrator.runTurn({
    state: {
      need: workingNeed,
      status: "intake",
      packageId: null,
      rfqDraftId: null,
      comparisonRunId: null,
      recommendation: null,
    },
    history: [],
    userMessage: initial,
    tools,
  });
  console.log("\n=== TURN 1 ===");
  console.log("reply:", turn1.reply);

  // persist state from turn 1
  await db
    .update(procurementRequests)
    .set({
      need: workingNeed,
      packageId: workingPackageId,
      rfqDraftId: workingRfqDraftId,
      status: turn1.stateUpdates.status ?? "intake",
      updatedAt: new Date(),
    })
    .where(eq(procurementRequests.id, request.id));

  if (!workingPackageId) throw new Error("turn 1 did not create a package");

  // ============== Register + "extract" 2 bids (as user would) ==============
  const makeBid = async (
    vendorId: string,
    docId: string,
    items: BidLineItem[],
    baseTotalCents: number,
    leadTimeWeeks: number,
  ): Promise<void> => {
    const existing = (
      await db
        .select()
        .from(bidsTable)
        .where(eq(bidsTable.documentId, docId))
        .limit(1)
    )[0];
    if (existing) {
      await db.delete(bidsTable).where(eq(bidsTable.id, existing.id));
    }
    await db.insert(bidsTable).values({
      projectId: project.id,
      packageId: workingPackageId!,
      vendorId,
      documentId: docId,
      status: "under_review",
      lineItems: items,
      baseTotal: baseTotalCents,
      leadTimeWeeks,
      extractedAt: new Date(),
      extractedBy: user.id,
    });
  };

  const acmeLines: BidLineItem[] = [
    { id: "a-1", description: "Footings 4000 psi", qty: 120, unit: "CY", unitPrice: 195, extended: 23400, category: "base", notes: null, source: null },
    { id: "a-2", description: "Slabs-on-grade 4000 psi", qty: 350, unit: "CY", unitPrice: 175, extended: 61250, category: "base", notes: null, source: null },
    { id: "a-3", description: "Walls 4000 psi", qty: 200, unit: "CY", unitPrice: 215, extended: 43000, category: "base", notes: null, source: null },
  ];
  const bayviewLines: BidLineItem[] = [
    { id: "b-1", description: "Footings 4000 psi", qty: 120, unit: "CY", unitPrice: 210, extended: 25200, category: "base", notes: null, source: null },
    { id: "b-2", description: "Slabs-on-grade 4000 psi", qty: 350, unit: "CY", unitPrice: 168, extended: 58800, category: "base", notes: null, source: null },
    { id: "b-3", description: "Walls 4000 psi", qty: 200, unit: "CY", unitPrice: 235, extended: 47000, category: "base", notes: null, source: null },
  ];
  await makeBid(vendorAId, bidDocA, acmeLines, 127_650 * 100, 6);
  await makeBid(vendorBId, bidDocB, bayviewLines, 131_000 * 100, 8);
  console.log("\n=== Registered 2 bids (Acme $127,650 / Bayview $131,000) ===");

  // ============== TURN 2 — agent compares + recommends ==============
  const turn2 = await orchestrator.runTurn({
    state: {
      need: workingNeed,
      status: "awaiting_bids",
      packageId: workingPackageId,
      rfqDraftId: workingRfqDraftId,
      comparisonRunId: null,
      recommendation: null,
    },
    history: [
      { role: "user", content: initial },
      { role: "assistant", content: turn1.reply },
    ],
    userMessage: "Bids are in — please compare.",
    tools,
  });
  console.log("\n=== TURN 2 ===");
  console.log("reply:", turn2.reply);
  console.log("actions:");
  for (const a of turn2.actions) console.log(`  - ${a.tool}: ${a.summary}`);

  // persist updates from turn 2
  const updates: Record<string, unknown> = { updatedAt: new Date() };
  if (turn2.stateUpdates.status) updates.status = turn2.stateUpdates.status;
  if (turn2.stateUpdates.comparisonRunId !== undefined)
    updates.comparisonRunId = turn2.stateUpdates.comparisonRunId;
  if (turn2.stateUpdates.recommendation !== undefined)
    updates.recommendation = turn2.stateUpdates.recommendation;
  await db.update(procurementRequests).set(updates).where(eq(procurementRequests.id, request.id));

  const final = (
    await db.select().from(procurementRequests).where(eq(procurementRequests.id, request.id)).limit(1)
  )[0]!;
  console.log("\n=== FINAL DB STATE ===");
  console.log("status:", final.status);
  console.log("comparisonRunId:", final.comparisonRunId);
  console.log("recommendation:", final.recommendation);

  const errors: string[] = [];
  if (final.status !== "recommended")
    errors.push(`status: expected recommended, got ${final.status}`);
  if (!final.comparisonRunId) errors.push("expected comparisonRunId set");
  if (!final.recommendation?.includes("Acme")) {
    errors.push(`expected Acme in recommendation, got: ${final.recommendation}`);
  }

  if (errors.length > 0) {
    console.error("\n❌ FAILED:");
    for (const e of errors) console.error(`  - ${e}`);
    process.exit(1);
  }
  console.log("\n✅ FULL FLOW PASSED — agent took a stated need to a vendor recommendation");

  // cleanup
  await db.delete(procurementRequests).where(eq(procurementRequests.id, request.id));
  if (final.comparisonRunId)
    await db.delete(comparisonRuns).where(eq(comparisonRuns.id, final.comparisonRunId));
  await db.delete(bidsTable).where(eq(bidsTable.documentId, bidDocA));
  await db.delete(bidsTable).where(eq(bidsTable.documentId, bidDocB));
  if (workingRfqDraftId) await db.delete(rfqDrafts).where(eq(rfqDrafts.id, workingRfqDraftId));
  await db.delete(packagesTable).where(eq(packagesTable.id, workingPackageId));
  await db.delete(vendors).where(eq(vendors.id, vendorAId));
  await db.delete(vendors).where(eq(vendors.id, vendorBId));
  await db.delete(documents).where(eq(documents.id, bidDocA));
  await db.delete(documents).where(eq(documents.id, bidDocB));
  console.log("(cleaned up)");
  process.exit(0);
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
