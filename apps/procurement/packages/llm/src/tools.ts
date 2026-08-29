import type Anthropic from "@anthropic-ai/sdk";

// Tool schemas exposed to the LLM. Inputs are validated by Zod on the registry
// side before any work happens.
export const toolDefinitions: Anthropic.Messages.Tool[] = [
  {
    name: "search_project_docs",
    description:
      "Search the project's parsed documents (specs, addenda, bids, submittals, etc.) for passages relevant to a question. Returns ranked snippets with document id, page number, and a chunk id you must cite when quoting.",
    input_schema: {
      type: "object",
      properties: {
        query: {
          type: "string",
          description: "Natural-language search query. Use specific construction terms.",
        },
        limit: {
          type: "integer",
          minimum: 1,
          maximum: 20,
          description: "Maximum number of results to return. Defaults to 8.",
        },
      },
      required: ["query"],
    },
  },
  {
    name: "get_page_text",
    description:
      "Fetch the full text of a specific page of a project document. Use this to expand on a search hit and quote precisely.",
    input_schema: {
      type: "object",
      properties: {
        documentId: { type: "string", format: "uuid" },
        page: { type: "integer", minimum: 1 },
      },
      required: ["documentId", "page"],
    },
  },
];

export const SYSTEM_PROMPT = `You are a construction procurement assistant working inside a project workspace.

Rules:
- Always call search_project_docs before making any factual claim from project documents.
- Cite every claim that came from a document with an inline marker like [doc:<documentId> p<page>]. The UI renders these as clickable chips, so include them in the prose, not just at the end.
- If you can't find evidence, say so plainly. Never invent clause numbers, prices, or dates.
- Keep replies tight and structured. Lead with the answer, then evidence.
- For comparisons or checklists, use a markdown table.

You can call tools multiple times. Stop when you have enough evidence to answer.`;
