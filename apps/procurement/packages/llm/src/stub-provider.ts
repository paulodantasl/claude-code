import type { Citation } from "@procurement/shared";
import type { LlmProvider, RunRequest, RunResult } from "./types.js";

// Used in dev/CI when no ANTHROPIC_API_KEY is set. Runs the search tool once,
// echoes the top hits, and returns a placeholder reply. Lets the full
// pipeline (auth → trpc → tool → DB → citations UI) work without burning
// tokens or needing a network key.
export function createStubProvider(): LlmProvider {
  return {
    name: "stub",
    async run(req: RunRequest): Promise<RunResult> {
      const search = await req.tools.search_project_docs(
        { query: req.userMessage, limit: 5 },
        req.ctx,
      );
      const citations: Citation[] = search.hits.map((h) => ({
        documentId: h.documentId,
        page: h.page,
        chunkId: h.chunkId,
        snippet: h.snippet,
      }));

      const lines = ["**(stub provider — no ANTHROPIC_API_KEY set)**", ""];
      if (search.hits.length === 0) {
        lines.push(
          "I could not find any relevant passages in this project's parsed documents. Upload a spec or addendum and try again.",
        );
      } else {
        lines.push(`Top ${search.hits.length} relevant passages for "${req.userMessage}":`);
        lines.push("");
        for (const hit of search.hits) {
          lines.push(
            `- ${hit.snippet.slice(0, 200)}${hit.snippet.length > 200 ? "…" : ""} [doc:${hit.documentId} p${hit.page}]`,
          );
        }
      }

      return {
        reply: lines.join("\n"),
        citations,
        trace: {
          model: "stub",
          stopReason: "stub",
          toolCalls: [
            {
              name: "search_project_docs",
              input: { query: req.userMessage, limit: 5 },
              output: search,
            },
          ],
        },
      };
    },
  };
}
