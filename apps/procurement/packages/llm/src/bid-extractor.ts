import Anthropic from "@anthropic-ai/sdk";
import { z } from "zod";

// What the extractor produces. The DB layer narrows this further (sourceChunkId
// becomes a UUID); keep this LLM-facing schema looser so we don't force the
// model to invent fields it can't see.
export const extractedLineItemSchema = z.object({
  description: z.string().min(1),
  qty: z.number().nullable().default(null),
  unit: z.string().nullable().default(null),
  unitPrice: z.number().nullable().default(null),
  extended: z.number().nullable().default(null),
  category: z
    .enum(["base", "alternate", "allowance", "exclusion"])
    .default("base"),
  notes: z.string().nullable().default(null),
  sourcePage: z.number().int().min(1).nullable().default(null),
  sourceSnippet: z.string().max(400).nullable().default(null),
});

export const extractionResultSchema = z.object({
  vendorName: z.string().nullable().default(null),
  leadTimeWeeks: z.number().int().min(0).nullable().default(null),
  baseTotal: z.number().nullable().default(null),
  lineItems: z.array(extractedLineItemSchema),
  assumptions: z.array(z.string()).default([]),
});

export type ExtractedLineItem = z.infer<typeof extractedLineItemSchema>;
export type ExtractionResult = z.infer<typeof extractionResultSchema>;

const EXTRACT_TOOL: Anthropic.Messages.Tool = {
  name: "submit_extracted_bid",
  description:
    "Return the structured contents of the bid. Call this exactly once.",
  input_schema: {
    type: "object",
    properties: {
      vendorName: { type: ["string", "null"] },
      leadTimeWeeks: { type: ["integer", "null"] },
      baseTotal: { type: ["number", "null"] },
      lineItems: {
        type: "array",
        items: {
          type: "object",
          properties: {
            description: { type: "string" },
            qty: { type: ["number", "null"] },
            unit: { type: ["string", "null"] },
            unitPrice: { type: ["number", "null"] },
            extended: { type: ["number", "null"] },
            category: {
              type: "string",
              enum: ["base", "alternate", "allowance", "exclusion"],
            },
            notes: { type: ["string", "null"] },
            sourcePage: { type: ["integer", "null"] },
            sourceSnippet: { type: ["string", "null"] },
          },
          required: ["description", "category"],
        },
      },
      assumptions: { type: "array", items: { type: "string" } },
    },
    required: ["lineItems"],
  },
};

const SYSTEM = `You are extracting line items from a vendor's construction bid. Be literal — do not invent items or prices.

Rules:
- One row per line item. If a row in the source has a subtotal beside other line items, include both as separate items.
- Categorize each item: "base" (in the base bid total), "alternate" (add/deduct outside base), "allowance" (placeholder), "exclusion" (explicitly excluded).
- Capture qty, unit, unitPrice, extended exactly as shown. Use null when not present (do not guess).
- For each item, sourcePage = the spreadsheet sheet number or PDF page where the row appears, and sourceSnippet = a short verbatim quote that contains the row.
- Capture overall lead time in weeks if stated.
- baseTotal is the sum the vendor calls "base bid" / "subtotal" — null if not explicit.
- assumptions: short notes about anything you couldn't reliably extract.

Call submit_extracted_bid exactly once with the result. Do not produce free-text response.`;

export interface BidExtractor {
  extract(opts: {
    bidText: string;
    documentTitle: string;
  }): Promise<ExtractionResult>;
}

export function createAnthropicExtractor(opts: {
  apiKey: string;
  model: string;
}): BidExtractor {
  const client = new Anthropic({ apiKey: opts.apiKey });
  return {
    async extract({ bidText, documentTitle }) {
      const resp = await client.messages.create({
        model: opts.model,
        max_tokens: 4000,
        system: SYSTEM,
        tools: [EXTRACT_TOOL],
        tool_choice: { type: "tool", name: EXTRACT_TOOL.name },
        messages: [
          {
            role: "user",
            content: `Document: ${documentTitle}\n\n--- BEGIN BID TEXT ---\n${bidText}\n--- END BID TEXT ---`,
          },
        ],
      });
      const toolUse = resp.content.find(
        (b): b is Anthropic.Messages.ToolUseBlock => b.type === "tool_use",
      );
      if (!toolUse) {
        throw new Error(
          "Model did not call submit_extracted_bid; cannot extract bid.",
        );
      }
      return extractionResultSchema.parse(toolUse.input);
    },
  };
}

// Fallback for offline dev. Walks the chunks heuristically and returns a
// plausible-looking extraction so the rest of the pipeline can be exercised.
export function createStubExtractor(): BidExtractor {
  return {
    async extract({ bidText }) {
      const lines = bidText.split("\n").map((l) => l.trim()).filter(Boolean);
      const items: ExtractedLineItem[] = [];
      for (const line of lines) {
        // Tab-separated rows: code, description, qty, unit, unitPrice, extended
        const parts = line.split("\t");
        if (parts.length < 4) continue;
        const numericExtended = num(parts[parts.length - 1]);
        const numericUnit = num(parts[parts.length - 2]);
        const description = parts[1] ?? parts[0];
        if (!description || description.length > 200) continue;
        items.push({
          description,
          qty: num(parts[2]),
          unit: parts[3] ?? null,
          unitPrice: numericUnit,
          extended: numericExtended,
          category: /alternate/i.test(description)
            ? "alternate"
            : /allowance/i.test(description)
              ? "allowance"
              : /exclud|exclusion/i.test(description)
                ? "exclusion"
                : "base",
          notes: null,
          sourcePage: 1,
          sourceSnippet: line.slice(0, 200),
        });
      }
      const baseTotal = items
        .filter((i) => i.category === "base")
        .reduce((acc, i) => acc + (i.extended ?? 0), 0);
      return {
        vendorName: null,
        leadTimeWeeks: null,
        baseTotal: baseTotal > 0 ? baseTotal : null,
        lineItems: items,
        assumptions: [
          "Stub extractor — heuristic only. Set ANTHROPIC_API_KEY for real extraction.",
        ],
      };
    },
  };
}

function num(s: string | undefined): number | null {
  if (!s) return null;
  const cleaned = s.replace(/[$,]/g, "").trim();
  if (!cleaned) return null;
  const n = Number(cleaned);
  return Number.isFinite(n) ? n : null;
}

export function selectExtractor(opts: { apiKey: string; model: string }): BidExtractor {
  if (opts.apiKey && opts.apiKey.trim().length > 0) {
    return createAnthropicExtractor(opts);
  }
  return createStubExtractor();
}
