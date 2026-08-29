import Anthropic from "@anthropic-ai/sdk";
import { z } from "zod";
import type { NeedSpec } from "@procurement/shared";

// ============================================================================
// The procurement orchestrator. Takes a procurement request's current state +
// a new user message, runs an LLM tool-use loop, and returns a structured
// turn: the message to show the user, any tool actions executed, any
// artifacts created, and proposed state updates (need / status / recommendation).
//
// Tools are NOT defined here in JS — they're declared as input schemas, and
// the caller (the request router) provides a tool-execution function that
// runs them against the DB / other routers. This keeps the orchestrator
// dependency-free and easy to swap providers.
// ============================================================================

export const needSpecSchema = z.object({
  item: z.string().nullable().default(null),
  quantity: z.number().nullable().default(null),
  unit: z.string().nullable().default(null),
  deadline: z.string().nullable().default(null),
  jurisdiction: z.string().nullable().default(null),
  trade: z.string().nullable().default(null),
  specs: z.array(z.string()).default([]),
  notes: z.string().nullable().default(null),
});

export type OrchestratorStatus =
  | "intake"
  | "sourcing"
  | "awaiting_bids"
  | "comparing"
  | "recommended"
  | "done"
  | "cancelled";

export interface OrchestratorState {
  need: NeedSpec;
  status: OrchestratorStatus;
  packageId: string | null;
  rfqDraftId: string | null;
  comparisonRunId: string | null;
  recommendation: string | null;
}

export interface OrchestratorHistoryMessage {
  role: "user" | "assistant";
  content: string;
}

export interface ToolAction {
  tool: string;
  input: unknown;
  ok: boolean;
  summary: string;
}
export interface ArtifactRef {
  kind: "package" | "rfq_draft" | "rfq_version" | "rfq_export" | "comparison_run";
  id: string;
  label: string;
}

export interface OrchestratorTurnResult {
  reply: string;
  stateUpdates: Partial<OrchestratorState>;
  actions: ToolAction[];
  artifacts: ArtifactRef[];
  trace: { model: string; iterations: number; stopReason: string | null };
}

export interface OrchestratorTools {
  /** Best-effort extraction of NeedSpec fields from free text. */
  extract_need: (input: { text: string }) => Promise<Partial<NeedSpec>>;

  /** Update / merge the current Need with new fields. Returns the new need. */
  update_need: (input: { fields: Partial<NeedSpec> }) => Promise<NeedSpec>;

  /** Search the project's parsed documents for relevant spec passages. */
  search_project_docs: (input: { query: string; limit?: number }) => Promise<{
    hits: Array<{
      documentId: string;
      documentTitle: string;
      page: number;
      chunkId: string;
      snippet: string;
      score: number;
    }>;
  }>;

  list_rfq_templates: (input: { trade?: string }) => Promise<
    Array<{ id: string; name: string; trade: string; division: string | null }>
  >;

  /** Create a sourcing package + RFQ draft from a template for this request. */
  create_package_and_rfq_draft: (input: {
    title: string;
    templateId: string;
  }) => Promise<{
    packageId: string;
    rfqDraftId: string;
    sections: Array<{ id: string; title: string }>;
  }>;

  /** Generate the body for one RFQ section, grounded in project docs. */
  generate_rfq_section: (input: { sectionId: string }) => Promise<{
    sectionId: string;
    citationCount: number;
    bodyPreview: string;
  }>;

  list_vendors: (input: { trade?: string }) => Promise<
    Array<{ id: string; name: string; trades: string[]; contactEmail: string | null }>
  >;

  list_bids: () => Promise<
    Array<{
      bidId: string;
      vendorName: string;
      documentTitle: string;
      extracted: boolean;
      baseTotalCents: number | null;
      leadTimeWeeks: number | null;
    }>
  >;

  /** Create a comparison_run snapshot across all extracted bids for the package. */
  create_comparison: (input: { title: string }) => Promise<{
    comparisonRunId: string;
    rowCount: number;
    flagCount: number;
    recommendedVendorId: string | null;
    recommendedVendorName: string | null;
    recommendationReason: string;
  }>;

  set_status: (input: { status: OrchestratorStatus }) => Promise<void>;

  set_recommendation: (input: { text: string }) => Promise<void>;

  /**
   * Freeze the current RFQ draft as a new immutable version, then send it
   * by email to the listed vendor recipients. Required: at least one
   * recipient with a real email. The caller (request router) handles
   * version creation and mail send + persisted send-log; the orchestrator
   * just decides who/when.
   */
  send_rfq_to_vendors: (input: {
    recipients: Array<{ vendorId?: string; email: string }>;
    responseDueDays?: number;
    notes?: string;
  }) => Promise<{
    versionId: string;
    versionNumber: number;
    attempted: number;
    sent: number;
    failed: number;
    failures: Array<{ email: string; error: string }>;
  }>;
}

const toolDefinitions: Anthropic.Messages.Tool[] = [
  {
    name: "extract_need",
    description:
      "Extract structured procurement fields (item, quantity, unit, deadline, trade, specs) from a piece of free text. Use when the user has just described their need and you haven't captured it yet.",
    input_schema: {
      type: "object",
      properties: { text: { type: "string" } },
      required: ["text"],
    },
  },
  {
    name: "update_need",
    description:
      "Merge fields into the current Need. Only pass fields that are confidently known or were just provided by the user. Returns the updated Need.",
    input_schema: {
      type: "object",
      properties: {
        fields: {
          type: "object",
          properties: {
            item: { type: ["string", "null"] },
            quantity: { type: ["number", "null"] },
            unit: { type: ["string", "null"] },
            deadline: { type: ["string", "null"] },
            jurisdiction: { type: ["string", "null"] },
            trade: { type: ["string", "null"] },
            specs: { type: "array", items: { type: "string" } },
            notes: { type: ["string", "null"] },
          },
        },
      },
      required: ["fields"],
    },
  },
  {
    name: "search_project_docs",
    description:
      "Search this project's parsed documents (specs, addenda) for relevant passages. Use BEFORE proposing specs in the Need or generating RFQ sections.",
    input_schema: {
      type: "object",
      properties: {
        query: { type: "string" },
        limit: { type: "integer", minimum: 1, maximum: 20 },
      },
      required: ["query"],
    },
  },
  {
    name: "list_rfq_templates",
    description: "List available RFQ templates. Filter by trade if known.",
    input_schema: {
      type: "object",
      properties: { trade: { type: "string" } },
    },
  },
  {
    name: "create_package_and_rfq_draft",
    description:
      "Create a sourcing package and an RFQ draft from a template. Returns the package id, draft id, and the list of section ids that will be generated. Call this once per request, after the Need is sufficiently complete and a matching templateId has been chosen.",
    input_schema: {
      type: "object",
      properties: {
        title: { type: "string" },
        templateId: { type: "string", format: "uuid" },
      },
      required: ["title", "templateId"],
    },
  },
  {
    name: "generate_rfq_section",
    description:
      "Generate the body for one RFQ section. The section will be filled from project docs with inline citations. Returns a short preview and the citation count.",
    input_schema: {
      type: "object",
      properties: { sectionId: { type: "string" } },
      required: ["sectionId"],
    },
  },
  {
    name: "list_vendors",
    description:
      "List vendors in the organization. Filter by trade to find ones who can quote this scope.",
    input_schema: {
      type: "object",
      properties: { trade: { type: "string" } },
    },
  },
  {
    name: "list_bids",
    description: "List bids registered against this request's package.",
    input_schema: { type: "object", properties: {} },
  },
  {
    name: "create_comparison",
    description:
      "Create an immutable comparison_run from all extracted bids for the package, and get a baseline recommendation. Requires at least 2 extracted bids.",
    input_schema: {
      type: "object",
      properties: { title: { type: "string" } },
      required: ["title"],
    },
  },
  {
    name: "set_status",
    description:
      "Update the request status. Valid: intake / sourcing / awaiting_bids / comparing / recommended / done / cancelled.",
    input_schema: {
      type: "object",
      properties: {
        status: {
          type: "string",
          enum: [
            "intake",
            "sourcing",
            "awaiting_bids",
            "comparing",
            "recommended",
            "done",
            "cancelled",
          ],
        },
      },
      required: ["status"],
    },
  },
  {
    name: "set_recommendation",
    description:
      "Set the final recommendation text for this request (which vendor / why). Call once near the end.",
    input_schema: {
      type: "object",
      properties: { text: { type: "string" } },
      required: ["text"],
    },
  },
  {
    name: "send_rfq_to_vendors",
    description:
      "Freeze the current RFQ draft as a new version and send it by email to the listed vendor recipients. Use ONLY when the user has confirmed the recipient list — never blindly send. Pass either vendorId (preferred — uses the vendor's stored contact email) or an explicit email for each recipient.",
    input_schema: {
      type: "object",
      properties: {
        recipients: {
          type: "array",
          minItems: 1,
          maxItems: 50,
          items: {
            type: "object",
            properties: {
              vendorId: { type: "string", format: "uuid" },
              email: { type: "string", format: "email" },
            },
            required: ["email"],
          },
        },
        responseDueDays: { type: "integer", minimum: 1, maximum: 120 },
        notes: { type: "string" },
      },
      required: ["recipients"],
    },
  },
];

const SYSTEM_PROMPT = `You are an autonomous construction procurement agent. The user states what they need; you take care of how to procure it.

Workflow you progress through:
1. intake — capture a Need (item, quantity, unit, deadline, trade, specs). Ask only the smallest set of follow-up questions needed to proceed.
2. sourcing — pick the best matching RFQ template, create a package + RFQ draft, generate every section grounded in the project's specs.
3. awaiting_bids — identify candidate vendors from the directory. **Confirm the recipient list with the user before calling send_rfq_to_vendors.** Then send the RFQ by email. After sending, wait for bids.
4. comparing — when 2+ bids are extracted, create a comparison run.
5. recommended — surface a clear recommendation (which vendor, why) with the comparison_run as evidence.

Email sending rules:
- NEVER call send_rfq_to_vendors without first showing the user the list of (vendorName → email) and getting confirmation in their reply.
- Prefer vendorId over a raw email so the vendor row is linked in the send log.
- Default responseDueDays to 10 unless the Need has a stricter deadline.

Rules:
- Tool-first. Always retrieve before claiming a spec exists.
- Be concise. Confirm decisions ("I'll use the concrete template …") before acting.
- Don't ask the user for information you can retrieve via search_project_docs.
- Match trade strings exactly to template trades you found via list_rfq_templates.
- After each meaningful action, end the turn with a short status message — what you did, what's next, and any question for the user. Keep it under 6 sentences.
- Do not call set_status redundantly. Only advance status when the underlying work is actually done.`;

const MAX_ITERATIONS = 12;

export interface OrchestratorProvider {
  name: string;
  runTurn(req: {
    state: OrchestratorState;
    history: OrchestratorHistoryMessage[];
    userMessage: string;
    tools: OrchestratorTools;
  }): Promise<OrchestratorTurnResult>;
}

export function createAnthropicOrchestrator(opts: {
  apiKey: string;
  model: string;
}): OrchestratorProvider {
  const client = new Anthropic({ apiKey: opts.apiKey });
  return {
    name: `anthropic:${opts.model}`,
    async runTurn({ state, history, userMessage, tools }) {
      const actions: ToolAction[] = [];
      const artifacts: ArtifactRef[] = [];
      const stateUpdates: Partial<OrchestratorState> = {};

      const messages: Anthropic.Messages.MessageParam[] = [
        ...history.map((h) => ({ role: h.role, content: h.content })),
        {
          role: "user",
          content: [
            { type: "text" as const, text: contextHeader(state) },
            { type: "text" as const, text: userMessage },
          ],
        },
      ];

      let iterations = 0;
      let stopReason: string | null = null;
      while (iterations < MAX_ITERATIONS) {
        iterations++;
        const resp = await client.messages.create({
          model: opts.model,
          max_tokens: 1500,
          system: SYSTEM_PROMPT,
          tools: toolDefinitions,
          messages,
        });
        stopReason = resp.stop_reason ?? null;
        messages.push({ role: "assistant", content: resp.content });
        if (resp.stop_reason !== "tool_use") {
          const text = resp.content
            .filter((b): b is Anthropic.Messages.TextBlock => b.type === "text")
            .map((b) => b.text)
            .join("\n")
            .trim();
          return {
            reply: text || "(no message)",
            stateUpdates,
            actions,
            artifacts,
            trace: { model: opts.model, iterations, stopReason },
          };
        }
        const toolResults: Anthropic.Messages.ToolResultBlockParam[] = [];
        for (const block of resp.content) {
          if (block.type !== "tool_use") continue;
          const result = await runTool(block, tools, stateUpdates, artifacts);
          actions.push({
            tool: block.name,
            input: block.input,
            ok: !result.isError,
            summary: result.summary,
          });
          toolResults.push({
            type: "tool_result",
            tool_use_id: block.id,
            content: JSON.stringify(result.payload),
            is_error: result.isError,
          });
        }
        messages.push({ role: "user", content: toolResults });
      }
      return {
        reply:
          "I ran out of iterations before finishing this turn. The state has been advanced where possible — please send another message to continue.",
        stateUpdates,
        actions,
        artifacts,
        trace: { model: opts.model, iterations, stopReason },
      };
    },
  };
}

function contextHeader(state: OrchestratorState): string {
  return [
    "Current request state:",
    `status=${state.status}`,
    `need=${JSON.stringify(state.need)}`,
    `packageId=${state.packageId ?? "null"}`,
    `rfqDraftId=${state.rfqDraftId ?? "null"}`,
    `comparisonRunId=${state.comparisonRunId ?? "null"}`,
    `recommendation=${state.recommendation ?? "null"}`,
    "",
    "User's new message:",
  ].join("\n");
}

async function runTool(
  block: Anthropic.Messages.ToolUseBlock,
  tools: OrchestratorTools,
  stateUpdates: Partial<OrchestratorState>,
  artifacts: ArtifactRef[],
): Promise<{ payload: unknown; isError: boolean; summary: string }> {
  try {
    switch (block.name) {
      case "extract_need": {
        const i = block.input as { text: string };
        const out = await tools.extract_need(i);
        return { payload: out, isError: false, summary: `extracted need fields: ${Object.keys(out).join(", ")}` };
      }
      case "update_need": {
        const i = block.input as { fields: Partial<NeedSpec> };
        const out = await tools.update_need(i);
        stateUpdates.need = out;
        return {
          payload: out,
          isError: false,
          summary: `updated need (${Object.keys(i.fields).join(", ")})`,
        };
      }
      case "search_project_docs": {
        const i = block.input as { query: string; limit?: number };
        const out = await tools.search_project_docs(i);
        return {
          payload: out,
          isError: false,
          summary: `search "${i.query}" → ${out.hits.length} hits`,
        };
      }
      case "list_rfq_templates": {
        const out = await tools.list_rfq_templates(block.input as { trade?: string });
        return { payload: out, isError: false, summary: `${out.length} templates` };
      }
      case "create_package_and_rfq_draft": {
        const i = block.input as { title: string; templateId: string };
        const out = await tools.create_package_and_rfq_draft(i);
        stateUpdates.packageId = out.packageId;
        stateUpdates.rfqDraftId = out.rfqDraftId;
        stateUpdates.status = "sourcing";
        artifacts.push({ kind: "package", id: out.packageId, label: i.title });
        artifacts.push({ kind: "rfq_draft", id: out.rfqDraftId, label: `RFQ draft (${i.title})` });
        return {
          payload: out,
          isError: false,
          summary: `package + RFQ draft created (${out.sections.length} sections)`,
        };
      }
      case "generate_rfq_section": {
        const i = block.input as { sectionId: string };
        const out = await tools.generate_rfq_section(i);
        return {
          payload: out,
          isError: false,
          summary: `generated section ${i.sectionId} (${out.citationCount} citations)`,
        };
      }
      case "list_vendors": {
        const out = await tools.list_vendors(block.input as { trade?: string });
        return { payload: out, isError: false, summary: `${out.length} vendors` };
      }
      case "list_bids": {
        const out = await tools.list_bids();
        return { payload: out, isError: false, summary: `${out.length} bids` };
      }
      case "create_comparison": {
        const i = block.input as { title: string };
        const out = await tools.create_comparison(i);
        stateUpdates.comparisonRunId = out.comparisonRunId;
        stateUpdates.status = "comparing";
        artifacts.push({ kind: "comparison_run", id: out.comparisonRunId, label: i.title });
        return {
          payload: out,
          isError: false,
          summary: `comparison run (${out.rowCount} lines, ${out.flagCount} flags)`,
        };
      }
      case "set_status": {
        const i = block.input as { status: OrchestratorStatus };
        await tools.set_status(i);
        stateUpdates.status = i.status;
        return { payload: { ok: true }, isError: false, summary: `status → ${i.status}` };
      }
      case "set_recommendation": {
        const i = block.input as { text: string };
        await tools.set_recommendation(i);
        stateUpdates.recommendation = i.text;
        stateUpdates.status = "recommended";
        return { payload: { ok: true }, isError: false, summary: `recommendation set` };
      }
      case "send_rfq_to_vendors": {
        const i = block.input as {
          recipients: Array<{ vendorId?: string; email: string }>;
          responseDueDays?: number;
          notes?: string;
        };
        const out = await tools.send_rfq_to_vendors(i);
        return {
          payload: out,
          isError: out.sent === 0,
          summary: `sent RFQ v${out.versionNumber} → ${out.sent}/${out.attempted} ok${out.failed > 0 ? `, ${out.failed} failed` : ""}`,
        };
      }
      default:
        return {
          payload: { error: `Unknown tool: ${block.name}` },
          isError: true,
          summary: `unknown tool ${block.name}`,
        };
    }
  } catch (err) {
    const message = err instanceof Error ? err.message : String(err);
    return { payload: { error: message }, isError: true, summary: `error: ${message}` };
  }
}

// ============================================================================
// Stub orchestrator: a deterministic state machine that mimics the LLM agent
// for offline development. It will progress a request based on what's missing.
// ============================================================================
export function createStubOrchestrator(): OrchestratorProvider {
  return {
    name: "stub",
    async runTurn({ state, userMessage, tools }) {
      const actions: ToolAction[] = [];
      const artifacts: ArtifactRef[] = [];
      const stateUpdates: Partial<OrchestratorState> = {};
      const record = (tool: string, input: unknown, ok: boolean, summary: string) =>
        actions.push({ tool, input, ok, summary });

      // INTAKE
      if (state.status === "intake" && !state.need.item) {
        const fields = await tools.extract_need({ text: userMessage });
        record("extract_need", { text: userMessage }, true, `extracted ${Object.keys(fields).join(", ")}`);
        const merged = await tools.update_need({ fields });
        stateUpdates.need = merged;
        record("update_need", { fields }, true, "merged need");
        const missing = missingFields(merged);
        if (missing.length > 0) {
          return reply(
            stateUpdates,
            actions,
            artifacts,
            `Got it. I have **${merged.item ?? "an item"}**${merged.quantity != null ? `, ${merged.quantity} ${merged.unit ?? "(units?)"}` : ""}. To proceed I still need: ${missing.join(", ")}. Could you provide those?`,
          );
        }
      }
      if (state.status === "intake" && state.need.item && missingFields(state.need).length > 0) {
        // user is filling in gaps
        const fields = await tools.extract_need({ text: userMessage });
        record("extract_need", { text: userMessage }, true, "follow-up fields");
        const merged = await tools.update_need({ fields });
        stateUpdates.need = merged;
        record("update_need", { fields }, true, "merged");
        const missing = missingFields(merged);
        if (missing.length > 0) {
          return reply(
            stateUpdates,
            actions,
            artifacts,
            `Thanks. Still need: ${missing.join(", ")}.`,
          );
        }
      }

      const currentNeed = stateUpdates.need ?? state.need;

      // SOURCING — create package + RFQ draft if not already done
      if (state.status === "intake" && missingFields(currentNeed).length === 0 && !state.rfqDraftId) {
        let templates = await tools.list_rfq_templates({ trade: currentNeed.trade ?? undefined });
        record("list_rfq_templates", { trade: currentNeed.trade }, true, `${templates.length} templates`);
        if (templates.length === 0) {
          // Fallback to general template
          const all = await tools.list_rfq_templates({});
          templates = all.filter((t) => t.trade === "general");
          record("list_rfq_templates", { trade: "general" }, true, `${templates.length} fallback templates`);
        }
        const tpl = templates[0];
        if (!tpl) {
          return reply(
            stateUpdates,
            actions,
            artifacts,
            `I couldn't find an RFQ template for trade "${currentNeed.trade}" and no general fallback is seeded. Add one in packages/db/src/templates.ts.`,
          );
        }
        const itemShort = (currentNeed.item ?? "").slice(0, 60).replace(/[…\s]+$/, "");
        const title = `${itemShort} — ${currentNeed.quantity} ${currentNeed.unit}`;
        const out = await tools.create_package_and_rfq_draft({ title, templateId: tpl.id });
        stateUpdates.packageId = out.packageId;
        stateUpdates.rfqDraftId = out.rfqDraftId;
        stateUpdates.status = "sourcing";
        artifacts.push({ kind: "package", id: out.packageId, label: title });
        artifacts.push({ kind: "rfq_draft", id: out.rfqDraftId, label: `RFQ — ${title}` });
        record(
          "create_package_and_rfq_draft",
          { title, templateId: tpl.id },
          true,
          `created (${out.sections.length} sections)`,
        );
        for (const sec of out.sections) {
          const r = await tools.generate_rfq_section({ sectionId: sec.id });
          record("generate_rfq_section", { sectionId: sec.id }, true, `${sec.title} (${r.citationCount} cites)`);
        }
        const vendors = await tools.list_vendors({ trade: currentNeed.trade ?? undefined });
        record("list_vendors", { trade: currentNeed.trade }, true, `${vendors.length} vendors`);
        stateUpdates.status = "awaiting_bids";
        return reply(
          stateUpdates,
          actions,
          artifacts,
          [
            `RFQ ready — package and draft created from template **${tpl.name}**, all ${out.sections.length} sections generated.`,
            vendors.length > 0
              ? `Matching vendors in your directory: ${vendors.map((v) => v.name).join(", ")}. Send the RFQ and upload bids here when received.`
              : `No vendors matched trade "${currentNeed.trade}" in your directory — add some, then send the RFQ. Upload bid documents and register them here once received.`,
          ].join(" "),
        );
      }

      // AWAITING_BIDS / COMPARING — check bids and compare if we have ≥2 extracted
      if (state.status === "awaiting_bids" || state.status === "sourcing") {
        const bids = await tools.list_bids();
        record("list_bids", {}, true, `${bids.length} bids`);
        const extracted = bids.filter((b) => b.extracted);
        if (extracted.length >= 2) {
          const out = await tools.create_comparison({
            title: `Comparison — ${currentNeed.item ?? "request"}`,
          });
          stateUpdates.comparisonRunId = out.comparisonRunId;
          stateUpdates.status = "comparing";
          artifacts.push({
            kind: "comparison_run",
            id: out.comparisonRunId,
            label: `Comparison (${extracted.length} vendors)`,
          });
          record("create_comparison", {}, true, `${out.rowCount} lines, ${out.flagCount} flags`);
          if (out.recommendedVendorName) {
            await tools.set_recommendation({ text: out.recommendationReason });
            stateUpdates.status = "recommended";
            stateUpdates.recommendation = out.recommendationReason;
            record("set_recommendation", {}, true, "set");
            return reply(
              stateUpdates,
              actions,
              artifacts,
              `Comparison built across ${extracted.length} vendors. **Recommendation:** ${out.recommendedVendorName}. ${out.recommendationReason}`,
            );
          }
          return reply(
            stateUpdates,
            actions,
            artifacts,
            `Comparison built — ${out.rowCount} lines, ${out.flagCount} flags raised. Review the comparison and pick a vendor.`,
          );
        }
        if (bids.length === 0) {
          return reply(
            stateUpdates,
            actions,
            artifacts,
            `Waiting on bids. Upload bid documents (PDF/XLSX), then register them under the package — I'll extract + compare once you have ≥2.`,
          );
        }
        const needExtract = bids.filter((b) => !b.extracted);
        return reply(
          stateUpdates,
          actions,
          artifacts,
          `${bids.length} bid(s) registered, ${extracted.length} extracted. ${needExtract.length > 0 ? `Click "Extract" on: ${needExtract.map((b) => b.vendorName).join(", ")}.` : "Need at least 2 extracted to compare."}`,
        );
      }

      // RECOMMENDED / DONE
      if (state.status === "recommended" || state.status === "comparing") {
        return reply(
          stateUpdates,
          actions,
          artifacts,
          state.recommendation
            ? `Recommendation already set: ${state.recommendation}`
            : "Comparison is ready — review it and confirm a vendor.",
        );
      }

      return reply(
        stateUpdates,
        actions,
        artifacts,
        "(stub orchestrator) I'm not sure what to do with that. Status is " + state.status + ".",
      );
    },
  };
}

function missingFields(need: NeedSpec): string[] {
  const missing: string[] = [];
  if (!need.item) missing.push("item description");
  if (need.quantity == null) missing.push("quantity");
  if (!need.unit) missing.push("unit (CY, tons, each, etc.)");
  if (!need.trade) missing.push("trade (concrete / structural_steel / drywall)");
  return missing;
}

function reply(
  stateUpdates: Partial<OrchestratorState>,
  actions: ToolAction[],
  artifacts: ArtifactRef[],
  message: string,
): OrchestratorTurnResult {
  return {
    reply: message,
    stateUpdates,
    actions,
    artifacts,
    trace: { model: "stub", iterations: 1, stopReason: "stub" },
  };
}

export function selectOrchestrator(opts: {
  apiKey: string;
  model: string;
}): OrchestratorProvider {
  if (opts.apiKey && opts.apiKey.trim().length > 0) {
    return createAnthropicOrchestrator(opts);
  }
  return createStubOrchestrator();
}
