import type { Provider } from "./settings-api";

/** Marks of the services SmartKOL connects to (favicons from their own sites, kept in public/logos). */
export const LOGOS: Record<string, string> = { apify: "/logos/apify.ico", openrouter: "/logos/openrouter.png" };

export const PROVIDER_NAMES: Record<Provider, string> = { openrouter: "OpenRouter", anthropic: "Anthropic", custom: "Custom endpoint" };
