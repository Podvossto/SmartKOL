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

export type LlmPing = {
  model: string;
  reply: string;
  latency_ms: number;
  input_tokens: number | null;
  output_tokens: number | null;
  cost_usd: number | null;
};

async function call<T>(method: string, path: string, body?: unknown): Promise<T> {
  const res = await fetch(`/api/settings${path}`, {
    method,
    headers: body ? { "Content-Type": "application/json" } : undefined,
    body: body ? JSON.stringify(body) : undefined,
    cache: "no-store",
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const detail = data?.detail;
    throw new Error(typeof detail === "string" ? detail : "Request failed");
  }
  return data as T;
}

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
  testLlm: () => call<LlmPing>("POST", "/llm/test"),
  exchangeOpenRouter: (code: string, code_verifier: string) =>
    call<SettingsView>("POST", "/openrouter/exchange", { code, code_verifier }),
};
