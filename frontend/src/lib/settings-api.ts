import { request } from "./http";

export type Provider = "openrouter" | "anthropic" | "custom";

export type SettingsView = {
  apify: { configured: boolean; source: "ui" | "env" | "none"; masked: string | null };
  llm: {
    configured: boolean;
    source: "ui" | "env" | "none";
    auth: "oauth" | "manual" | "env" | null;
    provider: Provider | null;
    protocol: "openai" | "anthropic" | null;
    base_url: string | null;
    model: string | null;
    masked: string | null;
  };
  presets: Record<string, { protocol: string; base_url: string; model: string }>;
};

export type ApifyAccount = {
  username: string;
  plan: string;
  usage_usd: number;
  limit_usd: number;
  remaining_usd: number;
  cycle_end: string | null;
};

export type LlmBalance = { usage_usd: number | null; limit_usd: number | null; remaining_usd: number | null };

export type LlmPing = {
  model: string;
  reply: string;
  latency_ms: number;
  input_tokens: number | null;
  output_tokens: number | null;
  cost_usd: number | null;
};

/** One prompt the AI is given. Only `text` (the instructions) can be edited; `output_format` is fixed. */
export type PromptView = {
  id: string;
  title: string;
  description: string;
  used_when: string;
  text: string;
  default: string;
  edited: boolean;
  output_format: string;
};

const call = <T>(method: string, path: string, body?: unknown) => request<T>(method, `/api/settings${path}`, body);

export const settingsApi = {
  get: () => call<SettingsView>("GET", ""),
  saveApify: (token: string) => call<SettingsView>("PUT", "/apify", { token }),
  clearApify: () => call<SettingsView>("DELETE", "/apify"),
  testApify: () => call<ApifyAccount>("POST", "/apify/test"),
  saveLlm: (body: {
    provider: Provider;
    api_key?: string;
    model?: string;
    protocol?: string;
    base_url?: string;
  }) => call<SettingsView>("PUT", "/llm", body),
  clearLlm: () => call<SettingsView>("DELETE", "/llm"),
  llmBalance: () => call<LlmBalance>("POST", "/llm/balance"),
  testLlm: () => call<LlmPing>("POST", "/llm/test"),
  prompts: () => call<PromptView[]>("GET", "/prompts"),
  savePrompt: (id: string, text: string) => call<PromptView>("PUT", `/prompts/${id}`, { text }),
  resetPrompt: (id: string) => call<PromptView>("DELETE", `/prompts/${id}`),
  exchangeOpenRouter: (code: string, code_verifier: string) =>
    call<SettingsView>("POST", "/openrouter/exchange", { code, code_verifier }),
};
