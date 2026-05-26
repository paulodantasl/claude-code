import type { FilledSection, RfqSectionSpec } from "@procurement/db";
import type { ToolRegistry } from "@procurement/llm";
import { selectProvider } from "@procurement/llm";
import { env } from "@/lib/env";
import { searchProjectDocs, getPageText } from "./search";

const provider = selectProvider({
  apiKey: env.ANTHROPIC_API_KEY,
  model: env.ANTHROPIC_MODEL,
});

const RFQ_SECTION_SYSTEM_PROMPT = `You are drafting one section of an RFQ (Request for Quote) document for a construction procurement team.

Rules:
- Always call search_project_docs first to find relevant spec clauses, addenda, and project notes before writing.
- Write professional, terse RFQ prose. Use markdown formatting (lists, sub-headings as needed).
- Cite every factual claim from a project document with an inline marker like [doc:<documentId> p<page>]. The UI renders these as clickable chips back to the source page.
- If the project corpus has no evidence for a required statement, write the canonical industry-standard wording but mark it with "(no project source — confirm with PM)".
- Do not include the section title in your output — just the body.
- Keep the section focused; do not stray into other sections.`;

export interface GenerateInput {
  projectId: string;
  userId: string;
  section: RfqSectionSpec;
  rfqTitle: string;
  projectName: string;
}

export async function generateRfqSection(input: GenerateInput): Promise<FilledSection> {
  const tools: ToolRegistry = {
    search_project_docs: async (toolInput) => ({
      hits: await searchProjectDocs(
        input.projectId,
        toolInput.query,
        toolInput.limit ?? 8,
      ),
    }),
    get_page_text: async (toolInput) =>
      getPageText(input.projectId, toolInput.documentId, toolInput.page),
  };

  const userMessage = [
    `RFQ: ${input.rfqTitle}`,
    `Project: ${input.projectName}`,
    `Section: ${input.section.title}`,
    "",
    "Brief:",
    input.section.prompt,
  ].join("\n");

  const result = await provider.run({
    systemPrompt: RFQ_SECTION_SYSTEM_PROMPT,
    history: [],
    userMessage,
    tools,
    ctx: { projectId: input.projectId, userId: input.userId },
  });

  return {
    id: input.section.id,
    title: input.section.title,
    body: result.reply,
    citations: result.citations,
    generatedAt: new Date().toISOString(),
    editedAt: null,
  };
}
