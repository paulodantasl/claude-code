import type { Citation, SearchHit } from "@procurement/shared";

export type ToolName = "search_project_docs" | "get_page_text";

export interface SearchProjectDocsInput {
  query: string;
  limit?: number;
}
export interface SearchProjectDocsOutput {
  hits: SearchHit[];
}

export interface GetPageTextInput {
  documentId: string;
  page: number;
}
export interface GetPageTextOutput {
  documentTitle: string;
  page: number;
  text: string;
}

export interface ToolContext {
  projectId: string;
  userId: string;
}

export interface ToolRegistry {
  search_project_docs: (
    input: SearchProjectDocsInput,
    ctx: ToolContext,
  ) => Promise<SearchProjectDocsOutput>;
  get_page_text: (
    input: GetPageTextInput,
    ctx: ToolContext,
  ) => Promise<GetPageTextOutput>;
}

export interface RunResult {
  reply: string;
  citations: Citation[];
  trace: {
    toolCalls: Array<{
      name: ToolName;
      input: unknown;
      output: unknown;
    }>;
    model: string;
    stopReason?: string;
  };
}

export interface RunRequest {
  systemPrompt?: string;
  history: Array<{ role: "user" | "assistant"; content: string }>;
  userMessage: string;
  tools: ToolRegistry;
  ctx: ToolContext;
}

export interface LlmProvider {
  name: string;
  run(req: RunRequest): Promise<RunResult>;
}
