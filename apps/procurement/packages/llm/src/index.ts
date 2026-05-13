export * from "./types.js";
export { SYSTEM_PROMPT, toolDefinitions } from "./tools.js";
export { createAnthropicProvider } from "./anthropic-provider.js";
export { createStubProvider } from "./stub-provider.js";

import { createAnthropicProvider } from "./anthropic-provider.js";
import { createStubProvider } from "./stub-provider.js";
import type { LlmProvider } from "./types.js";

export function selectProvider(opts: {
  apiKey: string;
  model: string;
}): LlmProvider {
  if (opts.apiKey && opts.apiKey.trim().length > 0) {
    return createAnthropicProvider(opts);
  }
  return createStubProvider();
}
