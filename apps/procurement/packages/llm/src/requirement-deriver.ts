import Anthropic from "@anthropic-ai/sdk";
import { z } from "zod";
import type { SearchHit } from "@procurement/shared";

export const derivedRequirementSchema = z.object({
  label: z.string().min(1).max(200),
  description: z.string().max(1000).default(""),
  artifactKind: z
    .enum(["submittal", "sds", "warranty", "coi", "lien_waiver", "other"])
    .default("submittal"),
  severity: z.enum(["required", "recommended", "optional"]).default("required"),
  sourceClause: z.string().max(300).nullable().default(null),
  sourcePage: z.number().int().min(1).nullable().default(null),
  sourceSnippet: z.string().max(400).nullable().default(null),
});

export const derivationResultSchema = z.object({
  requirements: z.array(derivedRequirementSchema),
});

export type DerivedRequirement = z.infer<typeof derivedRequirementSchema>;
export type DerivationResult = z.infer<typeof derivationResultSchema>;

const DERIVE_TOOL: Anthropic.Messages.Tool = {
  name: "submit_requirements",
  description:
    "Return the list of compliance/submittal requirements derived from the spec text. Call exactly once.",
  input_schema: {
    type: "object",
    properties: {
      requirements: {
        type: "array",
        items: {
          type: "object",
          properties: {
            label: { type: "string" },
            description: { type: "string" },
            artifactKind: {
              type: "string",
              enum: ["submittal", "sds", "warranty", "coi", "lien_waiver", "other"],
            },
            severity: {
              type: "string",
              enum: ["required", "recommended", "optional"],
            },
            sourceClause: { type: ["string", "null"] },
            sourcePage: { type: ["integer", "null"] },
            sourceSnippet: { type: ["string", "null"] },
          },
          required: ["label", "artifactKind", "severity"],
        },
      },
    },
    required: ["requirements"],
  },
};

const SYSTEM = `You extract compliance and submittal requirements from construction spec excerpts.

Rules:
- A requirement is anything the vendor must SUBMIT or PROVIDE: submittals (mix designs, shop drawings, product data), SDS sheets, warranties, certificates of insurance, lien waivers, compliance certs, qualifications, etc.
- One requirement per distinct deliverable. Do not merge unrelated items.
- artifactKind: submittal / sds / warranty / coi / lien_waiver / other.
- severity: "required" if the spec uses "shall"/"must"/"required"; "recommended" for "should"; "optional" otherwise.
- For each requirement set sourceClause (e.g., "03 30 00 - 3.3.A"), sourcePage (the page it appeared on), and a short verbatim sourceSnippet.
- Only include requirements you can ground in the provided text. Do not invent.

Call submit_requirements exactly once.`;

export interface RequirementDeriver {
  derive(opts: { specText: string }): Promise<DerivationResult>;
}

export function createAnthropicDeriver(opts: {
  apiKey: string;
  model: string;
}): RequirementDeriver {
  const client = new Anthropic({ apiKey: opts.apiKey });
  return {
    async derive({ specText }) {
      const resp = await client.messages.create({
        model: opts.model,
        max_tokens: 4000,
        system: SYSTEM,
        tools: [DERIVE_TOOL],
        tool_choice: { type: "tool", name: DERIVE_TOOL.name },
        messages: [
          {
            role: "user",
            content: `--- BEGIN SPEC TEXT ---\n${specText}\n--- END SPEC TEXT ---`,
          },
        ],
      });
      const toolUse = resp.content.find(
        (b): b is Anthropic.Messages.ToolUseBlock => b.type === "tool_use",
      );
      if (!toolUse) {
        throw new Error("Model did not return requirements.");
      }
      return derivationResultSchema.parse(toolUse.input);
    },
  };
}

// Heuristic offline deriver: scans for lines mentioning submittal-ish keywords.
export function createStubDeriver(): RequirementDeriver {
  return {
    async derive({ specText }) {
      const requirements: DerivedRequirement[] = [];
      const lines = specText.split("\n");
      let page = 1;
      for (const raw of lines) {
        const line = raw.trim();
        const pageMatch = line.match(/^\[page (\d+)\]/);
        if (pageMatch) {
          page = Number(pageMatch[1]);
          continue;
        }
        if (!/submit|submittal|certificate|warranty|data sheet|sds|compliance/i.test(line)) {
          continue;
        }
        if (line.length < 8 || line.length > 240) continue;
        requirements.push({
          label: line.replace(/^[A-Z0-9.\s]+/, "").slice(0, 120) || line.slice(0, 120),
          description: line,
          artifactKind: /sds|data sheet/i.test(line)
            ? "sds"
            : /warranty/i.test(line)
              ? "warranty"
              : /insurance|coi/i.test(line)
                ? "coi"
                : "submittal",
          severity: /\bshall\b|\bmust\b|required/i.test(line) ? "required" : "recommended",
          sourceClause: null,
          sourcePage: page,
          sourceSnippet: line.slice(0, 200),
        });
      }
      return { requirements: dedupe(requirements) };
    },
  };
}

function dedupe(reqs: DerivedRequirement[]): DerivedRequirement[] {
  const seen = new Set<string>();
  const out: DerivedRequirement[] = [];
  for (const r of reqs) {
    const key = r.label.toLowerCase();
    if (seen.has(key)) continue;
    seen.add(key);
    out.push(r);
  }
  return out;
}

export function selectDeriver(opts: { apiKey: string; model: string }): RequirementDeriver {
  if (opts.apiKey && opts.apiKey.trim().length > 0) {
    return createAnthropicDeriver(opts);
  }
  return createStubDeriver();
}

// Helper: turn search hits into a flat spec text blob with page markers.
export function hitsToSpecText(hits: SearchHit[]): string {
  return hits.map((h) => `[page ${h.page}]\n${h.snippet}`).join("\n\n");
}
