"use client";

import { Check } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { InfoTip } from "@/components/ui/info-tip";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { LOGOS, PROVIDER_NAMES } from "@/lib/brand-logos";
import { startOpenRouterLogin } from "@/lib/pkce";
import { type LlmPing, type Provider, type SettingsView, settingsApi } from "@/lib/settings-api";
import { cn } from "@/lib/utils";

import { FieldNote, ServiceTitle, SourceBadge, errorMessage } from "./shared";

const PROVIDERS: { id: Provider; label: string; keyHint: string; models?: string }[] = [
  { id: "openrouter", label: "OpenRouter", keyHint: "sk-or-v1-…", models: "https://openrouter.ai/models" },
  { id: "anthropic", label: "Anthropic", keyHint: "sk-ant-api03-…", models: "https://docs.anthropic.com/en/docs/about-claude/models" },
  { id: "custom", label: "Custom", keyHint: "Your API key" },
];

const HOW = { oauth: "signed in with OpenRouter", manual: "saved key", env: "key from the server file" } as const;

export function LlmCard({ view, onChange }: { view: SettingsView; onChange: (v: SettingsView) => void }) {
  const llm = view.llm;
  const [provider, setProvider] = useState<Provider>(llm.provider ?? "openrouter");
  const [model, setModel] = useState(llm.model ?? view.presets.openrouter.model);
  const [protocol, setProtocol] = useState<"openai" | "anthropic">(llm.provider === "custom" && llm.protocol ? llm.protocol : "openai");
  const [baseUrl, setBaseUrl] = useState(llm.provider === "custom" ? (llm.base_url ?? "") : "");
  const [apiKey, setApiKey] = useState("");
  const [useKey, setUseKey] = useState(false); // OpenRouter: paste a key instead of signing in
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [problems, setProblems] = useState<Partial<Record<"key" | "url" | "model", string>>>({});
  const [ping, setPing] = useState<LlmPing | null>(null);

  const hasSavedForProvider = llm.configured && llm.provider === provider;
  const preset = view.presets[provider]?.model ?? "";
  const info = PROVIDERS.find((p) => p.id === provider)!;
  const asksForKey = provider !== "openrouter" || useKey;
  const switching = llm.configured && llm.provider && llm.provider !== provider;

  function pickProvider(next: Provider) {
    setProvider(next);
    setError(null);
    setProblems({});
    setPing(null);
    setApiKey("");
    setUseKey(false);
    setModel(llm.provider === next && llm.model ? llm.model : (view.presets[next]?.model ?? ""));
  }

  async function run(action: () => Promise<void>) {
    setBusy(true);
    setError(null);
    setPing(null);
    try {
      await action();
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  function saveAndTest() {
    const found: typeof problems = {};
    if (asksForKey && !apiKey.trim() && !hasSavedForProvider) found.key = "Paste your API key first.";
    if (provider === "custom" && !/^https?:\/\/[^/\s]+/i.test(baseUrl.trim())) found.url = "Enter the full address, starting with https://";
    if (!model.trim()) found.model = "Enter a model name.";
    setProblems(found);
    if (Object.keys(found).length) return;
    return run(async () => {
      onChange(
        await settingsApi.saveLlm({
          provider,
          api_key: apiKey.trim() || undefined,
          model: model.trim() || undefined,
          ...(provider === "custom" ? { protocol, base_url: baseUrl } : {}),
        }),
      );
      setApiKey("");
      setUseKey(false);
      setPing(await settingsApi.testLlm());
    });
  }

  const testActive = () => run(async () => setPing(await settingsApi.testLlm()));
  const removeSaved = () => run(async () => onChange(await settingsApi.clearLlm()));
  const connectOpenRouter = () => run(startOpenRouterLogin);
  const clear = (k: keyof typeof problems) => setProblems((p) => ({ ...p, [k]: undefined }));

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex flex-wrap items-center gap-3">
          <ServiceTitle logo={llm.provider ? LOGOS[llm.provider] : undefined}>Language model</ServiceTitle> <SourceBadge source={llm.source} />
        </CardTitle>
        <CardDescription>Writes the brand profile and, later, judges how well creators fit.</CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        {llm.configured && llm.provider && llm.auth && (
          <p className="text-sm" role="status">
            <span className="text-muted-foreground">Active: </span>
            <strong className="font-medium">{PROVIDER_NAMES[llm.provider]}</strong> · {llm.model} <span className="text-muted-foreground">· {HOW[llm.auth]} {llm.masked}</span>
          </p>
        )}

        <div role="group" aria-label="Provider" className="flex w-fit max-w-full flex-wrap gap-1 rounded-full bg-muted p-1">
          {PROVIDERS.map((p) => (
            <button
              key={p.id}
              type="button"
              aria-pressed={provider === p.id}
              onClick={() => pickProvider(p.id)}
              className={cn("rounded-full px-4 py-1.5 text-sm transition-all duration-300", provider === p.id ? "bg-white font-medium shadow-sm" : "text-muted-foreground hover:text-foreground")}
            >
              {p.label}
            </button>
          ))}
        </div>
        {switching && <FieldNote>Saving will switch from {PROVIDER_NAMES[llm.provider!]} to {PROVIDER_NAMES[provider]}.</FieldNote>}

        {provider === "openrouter" && !useKey && (
          <div className="flex flex-col gap-3 rounded-2xl bg-accent p-4">
            <p className="text-sm">Sign in to OpenRouter and SmartKOL creates a key and saves it for you. Nothing to copy.</p>
            <div className="flex flex-wrap items-center gap-4">
              <Button variant={hasSavedForProvider ? "outline" : "default"} onClick={connectOpenRouter} disabled={busy}>
                {hasSavedForProvider ? "Sign in again" : "Connect with OpenRouter"}
              </Button>
              <button type="button" onClick={() => setUseKey(true)} className="text-sm text-primary underline-offset-4 hover:underline">
                Use an API key instead
              </button>
            </div>
          </div>
        )}

        {provider === "custom" && (
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="flex flex-col gap-2">
              <Label>API style</Label>
              <div role="group" aria-label="API style" className="flex w-fit gap-1 rounded-full bg-muted p-1">
                {(["openai", "anthropic"] as const).map((p) => (
                  <button key={p} type="button" aria-pressed={protocol === p} onClick={() => setProtocol(p)} className={cn("rounded-full px-3 py-1.5 text-sm transition-all duration-300", protocol === p ? "bg-white font-medium shadow-sm" : "text-muted-foreground hover:text-foreground")}>
                    {p === "openai" ? "OpenAI-compatible" : "Anthropic"}
                  </button>
                ))}
              </div>
            </div>
            <div className="flex flex-col gap-2">
              <Label htmlFor="llm-base">Base URL</Label>
              <Input id="llm-base" placeholder="https://api.example.com/v1" value={baseUrl} aria-invalid={problems.url ? true : undefined} onChange={(e) => { setBaseUrl(e.target.value); clear("url"); }} />
              {problems.url && <FieldNote error>{problems.url}</FieldNote>}
            </div>
          </div>
        )}

        <div className="grid gap-4 sm:grid-cols-2">
          {asksForKey && (
            <div className="flex flex-col gap-2">
              <Label htmlFor="llm-key">API key</Label>
              <Input
                id="llm-key"
                type="password"
                autoComplete="off"
                placeholder={hasSavedForProvider ? "Using the saved key. Paste to replace it" : info.keyHint}
                value={apiKey}
                aria-invalid={problems.key ? true : undefined}
                onChange={(e) => { setApiKey(e.target.value); clear("key"); }}
              />
              {problems.key && <FieldNote error>{problems.key}</FieldNote>}
              {provider === "openrouter" && (
                <button type="button" onClick={() => setUseKey(false)} className="w-fit text-xs text-primary underline-offset-4 hover:underline">
                  Sign in instead
                </button>
              )}
            </div>
          )}
          <div className="flex flex-col gap-2">
            <Label htmlFor="llm-model">Model</Label>
            <Input id="llm-model" placeholder={preset || "e.g. claude-haiku-5-5"} value={model} aria-invalid={problems.model ? true : undefined} onChange={(e) => { setModel(e.target.value); clear("model"); }} />
            {problems.model && <FieldNote error>{problems.model}</FieldNote>}
            <p className="flex flex-wrap gap-x-3 text-xs text-muted-foreground">
              {preset && model !== preset && (
                <button type="button" onClick={() => setModel(preset)} className="text-primary underline-offset-4 hover:underline">
                  Use the default ({preset})
                </button>
              )}
              {info.models && (
                <a href={info.models} target="_blank" rel="noreferrer" className="text-primary underline-offset-4 hover:underline">
                  See the model list
                </a>
              )}
            </p>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-3">
          {(asksForKey || hasSavedForProvider) && (
            <Button onClick={saveAndTest} disabled={busy}>
              Save &amp; test
            </Button>
          )}
          {llm.configured && (
            <Button variant="outline" onClick={testActive} disabled={busy}>
              Test active model
            </Button>
          )}
          {llm.source === "ui" && (
            <Button variant="ghost" onClick={removeSaved} disabled={busy}>
              Remove saved key
            </Button>
          )}
        </div>

        {ping && (
          <p className="flex flex-wrap items-center gap-2 text-sm" role="status">
            <span className="grid size-5 place-items-center rounded-full bg-primary text-primary-foreground">
              <Check className="size-3" strokeWidth={3} />
            </span>
            Connected · {ping.model} replied in {(ping.latency_ms / 1000).toFixed(1)}s
            <InfoTip label="Details of the test" text="Details">
              <span>
                Reply: “{ping.reply}”
                {ping.input_tokens != null && ` · ${ping.input_tokens} in / ${ping.output_tokens} out tokens`}
              </span>
              {ping.cost_usd != null && <span>Test cost: ${ping.cost_usd.toFixed(6)}</span>}
            </InfoTip>
          </p>
        )}
        {error && (
          <p className="text-sm text-destructive" role="alert">
            {error}
          </p>
        )}
      </CardContent>
    </Card>
  );
}
