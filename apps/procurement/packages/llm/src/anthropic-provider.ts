import Anthropic from "@anthropic-ai/sdk";
import type { Citation } from "@procurement/shared";
import { SYSTEM_PROMPT, toolDefinitions } from "./tools.js";
import type {
  LlmProvider,
  RunRequest,
  RunResult,
  SearchProjectDocsInput,
  GetPageTextInput,
} from "./types.js";

const MAX_TOOL_ITERATIONS = 6;

interface AnthropicProviderOpts {
  apiKey: string;
  model: string;
}

export function createAnthropicProvider(opts: AnthropicProviderOpts): LlmProvider {
  const client = new Anthropic({ apiKey: opts.apiKey });
  const model = opts.model;

  return {
    name: `anthropic:${model}`,
    async run(req: RunRequest): Promise<RunResult> {
      const messages: Anthropic.Messages.MessageParam[] = [
        ...req.history.map((m) => ({ role: m.role, content: m.content })),
        { role: "user", content: req.userMessage },
      ];

      const trace: RunResult["trace"] = { toolCalls: [], model };
      const citations: Citation[] = [];

      for (let i = 0; i < MAX_TOOL_ITERATIONS; i++) {
        const resp = await client.messages.create({
          model,
          max_tokens: 1500,
          system: req.systemPrompt ?? SYSTEM_PROMPT,
          tools: toolDefinitions,
          messages,
        });
        trace.stopReason = resp.stop_reason ?? undefined;

        const assistantContent: Anthropic.Messages.ContentBlock[] = resp.content;
        messages.push({ role: "assistant", content: assistantContent });

        if (resp.stop_reason !== "tool_use") {
          const text = assistantContent
            .filter((b): b is Anthropic.Messages.TextBlock => b.type === "text")
            .map((b) => b.text)
            .join("\n");
          return { reply: text, citations, trace };
        }

        const toolResults: Anthropic.Messages.ToolResultBlockParam[] = [];
        for (const block of assistantContent) {
          if (block.type !== "tool_use") continue;
          const out = await invokeTool(block, req, citations);
          trace.toolCalls.push({
            name: block.name as RunResult["trace"]["toolCalls"][number]["name"],
            input: block.input,
            output: out.payload,
          });
          toolResults.push({
            type: "tool_result",
            tool_use_id: block.id,
            content: JSON.stringify(out.payload),
            is_error: out.isError,
          });
        }
        messages.push({ role: "user", content: toolResults });
      }

      return {
        reply:
          "I ran out of tool iterations before reaching a confident answer. Please try a more specific question or upload more source documents.",
        citations,
        trace,
      };
    },
  };
}

async function invokeTool(
  block: Anthropic.Messages.ToolUseBlock,
  req: RunRequest,
  citations: Citation[],
): Promise<{ payload: unknown; isError: boolean }> {
  try {
    if (block.name === "search_project_docs") {
      const input = block.input as SearchProjectDocsInput;
      const out = await req.tools.search_project_docs(input, req.ctx);
      // Accumulate citations from search hits; the model is instructed to cite
      // them inline. We pass them back so the UI can render chips even if the
      // model forgets a marker.
      for (const hit of out.hits) {
        if (!citations.some((c) => c.chunkId === hit.chunkId)) {
          citations.push({
            documentId: hit.documentId,
            page: hit.page,
            chunkId: hit.chunkId,
            snippet: hit.snippet,
          });
        }
      }
      return { payload: out, isError: false };
    }
    if (block.name === "get_page_text") {
      const input = block.input as GetPageTextInput;
      const out = await req.tools.get_page_text(input, req.ctx);
      return { payload: out, isError: false };
    }
    return { payload: { error: `Unknown tool: ${block.name}` }, isError: true };
  } catch (err) {
    return {
      payload: { error: err instanceof Error ? err.message : String(err) },
      isError: true,
    };
  }
}
