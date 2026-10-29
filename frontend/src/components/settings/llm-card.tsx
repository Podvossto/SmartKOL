"use client";

import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { startOpenRouterLogin } from "@/lib/pkce";
import { type LlmPing, type Provider, type SettingsView, settingsApi } from "@/lib/settings-api";

import { SourceBadge, errorMessage } from "./shared";

const PROVIDERS: { id: Provider; label: string; keyHint: string }[] = [
  { id: "openrouter", label: "OpenRouter", keyHint: "sk-or-v1-…" },
  { id: "anthropic", label: "Anthropic", keyHint: "sk-ant-api03-…" },
  { id: "custom", label: "Custom", keyHint: "API key" },
];

const AUTH_LABEL = { oauth: "connected with OpenRouter", manual: "pasted key", env: "credential/.env" } as const;

export function LlmCard({ view, onChange }: { view: SettingsView; onChange: (v: SettingsView) => void }) {
  const llm = view.llm;
  const [provider, setProvider] = useState<Provider>(llm.provider ?? "openrouter");
  const [model, setModel] = useState(llm.model ?? view.presets.openrouter.model);
  const [protocol, setProtocol] = useState<"openai" | "anthropic">(llm.provider === "custom" && llm.protocol ? llm.protocol : "openai");
  const [baseUrl, setBaseUrl] = useState(llm.provider === "custom" ? (llm.base_url ?? "") : "");
  const [apiKey, setApiKey] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [ping, setPing] = useState<LlmPing | null>(null);

  const hasSavedForProvider = llm.configured && llm.provider === provider;

  function pickProvider(next: Provider) {
    setProvider(next);
    setError(null);
    setPing(null);
    setApiKey("");
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

  const saveAndTest = () =>
    run(async () => {
      onChange(
        await settingsApi.saveLlm({
          provider,
          api_key: apiKey.trim() || undefined,
          model: model.trim() || undefined,
          ...(provider === "custom" ? { protocol, base_url: baseUrl } : {}),
        }),
      );
      setApiKey("");
      setPing(await settingsApi.testLlm());
    });

  const testOnly = () => run(async () => setPing(await settingsApi.testLlm()));
  const removeSaved = () => run(async () => onChange(await settingsApi.clearLlm()));
  const connectOpenRouter = () => run(startOpenRouterLogin);

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-3">
          Language model <SourceBadge source={llm.source} />
        </CardTitle>
        <CardDescription>
          Reads the brand and judges creator fit. Bring your own provider — usage is billed to your account.
        </CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        <div className="flex flex-wrap gap-2" role="group" aria-label="Provider">
          {PROVIDERS.map((p) => (
            <Button key={p.id} size="sm" variant={provider === p.id ? "default" : "outline"} onClick={() => pickProvider(p.id)}>
              {p.label}
            </Button>
          ))}
        </div>

        {llm.configured && llm.auth && (
          <p className="text-sm text-muted-foreground">
            Using {llm.provider} · {llm.model} · key {llm.masked} ({AUTH_LABEL[llm.auth]})
          </p>
        )}

        {provider === "openrouter" && (
          <div className="flex flex-col gap-2 rounded-lg bg-accent p-3">
            <p className="text-sm">Sign in once and OpenRouter issues a key to this app — no copy-paste.</p>
            <Button className="self-start" onClick={connectOpenRouter} disabled={busy}>
              Connect with OpenRouter
            </Button>
          </div>
        )}

        {provider === "custom" && (
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="flex flex-col gap-2">
              <Label>API style</Label>
              <div className="flex gap-2" role="group" aria-label="API style">
                {(["openai", "anthropic"] as const).map((p) => (
                  <Button key={p} size="sm" variant={protocol === p ? "default" : "outline"} onClick={() => setProtocol(p)}>
                    {p === "openai" ? "OpenAI-compatible" : "Anthropic"}
                  </Button>
                ))}
              </div>
            </div>
            <div className="flex flex-col gap-2">
              <Label htmlFor="llm-base">Base URL</Label>
              <Input id="llm-base" placeholder="https://api.example.com/v1" value={baseUrl} onChange={(e) => setBaseUrl(e.target.value)} />
            </div>
          </div>
        )}

        <div className="grid gap-4 sm:grid-cols-2">
          <div className="flex flex-col gap-2">
            <Label htmlFor="llm-key">{provider === "openrouter" ? "Or paste an API key" : "API key"}</Label>
            <Input
              id="llm-key"
              type="password"
              autoComplete="off"
              placeholder={hasSavedForProvider ? "Leave blank to keep the current key" : PROVIDERS.find((p) => p.id === provider)?.keyHint}
              value={apiKey}
              onChange={(e) => setApiKey(e.target.value)}
            />
          </div>
          <div className="flex flex-col gap-2">
            <Label htmlFor="llm-model">Model</Label>
            <Input id="llm-model" value={model} onChange={(e) => setModel(e.target.value)} />
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-3">
          <Button onClick={saveAndTest} disabled={busy || (!apiKey.trim() && !hasSavedForProvider)}>
            Save & test
          </Button>
          {llm.configured && (
            <Button variant="outline" onClick={testOnly} disabled={busy}>
              Test current
            </Button>
          )}
          {llm.source === "ui" && (
            <Button variant="outline" onClick={removeSaved} disabled={busy}>
              Remove saved key
            </Button>
          )}
        </div>

        {ping && (
          <p className="text-sm" role="status">
            Works — <strong>{ping.model}</strong> replied “{ping.reply}” in {(ping.latency_ms / 1000).toFixed(1)}s
            {ping.input_tokens != null && ` · ${ping.input_tokens} in / ${ping.output_tokens} out tokens`}
            {ping.cost_usd != null && ` · $${ping.cost_usd.toFixed(6)}`}
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
