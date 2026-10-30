"use client";

import { Check } from "lucide-react";
import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { LOGOS } from "@/lib/brand-logos";
import { type ApifyAccount, type SettingsView, settingsApi } from "@/lib/settings-api";

import { FieldNote, ServiceTitle, SourceBadge, errorMessage, usd } from "./shared";

export function ApifyCard({ view, onChange }: { view: SettingsView["apify"]; onChange: (v: SettingsView) => void }) {
  const [token, setToken] = useState("");
  const [replacing, setReplacing] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [fieldError, setFieldError] = useState<string | null>(null);
  const [account, setAccount] = useState<ApifyAccount | null>(null);
  const [checking, setChecking] = useState(view.configured);

  // Checking a token is free, so a connected account shows its state without being asked.
  useEffect(() => {
    if (!view.configured) return;
    let live = true;
    settingsApi
      .testApify()
      .then((a) => live && setAccount(a))
      .catch((err) => live && setError(errorMessage(err)))
      .finally(() => live && setChecking(false));
    return () => {
      live = false;
    };
  }, [view.configured, view.masked]);

  async function run(action: () => Promise<void>) {
    setBusy(true);
    setError(null);
    try {
      await action();
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  const test = () =>
    run(async () => {
      setAccount(null);
      setAccount(await settingsApi.testApify());
    });

  async function save() {
    if (!token.trim()) return setFieldError("Paste your Apify token first.");
    setFieldError(null);
    await run(async () => {
      setAccount(null);
      onChange(await settingsApi.saveApify(token));
      setToken("");
      setReplacing(false);
    });
  }

  const remove = () =>
    run(async () => {
      setAccount(null);
      onChange(await settingsApi.clearApify());
    });

  const showInput = !view.configured || replacing;

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex flex-wrap items-center gap-3">
          <ServiceTitle logo={LOGOS.apify}>Apify</ServiceTitle> <SourceBadge source={view.source} />
        </CardTitle>
        <CardDescription>
          Reads the Facebook and TikTok data.{" "}
          <a className="text-primary underline-offset-4 hover:underline" href="https://console.apify.com/settings/integrations" target="_blank" rel="noreferrer">
            Get a token
          </a>
          .
        </CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        {view.configured && (
          <p className="flex flex-wrap items-center gap-x-2 gap-y-1 text-sm" role="status">
            {checking || busy ? (
              <span className="text-muted-foreground">Checking…</span>
            ) : account ? (
              <>
                <span className="grid size-5 place-items-center rounded-full bg-primary text-primary-foreground">
                  <Check className="size-3" strokeWidth={3} />
                </span>
                <span>
                  Connected as <strong className="font-medium">{account.username}</strong> · {usd(account.remaining_usd)} left of {usd(account.limit_usd)} this month
                  {account.cycle_end && <span className="text-muted-foreground"> · resets {new Date(account.cycle_end).toLocaleDateString("en-GB", { day: "numeric", month: "short" })}</span>}
                </span>
              </>
            ) : null}
          </p>
        )}

        {showInput ? (
          <div className="flex flex-col gap-2">
            <Label htmlFor="apify-token">{view.configured ? "New API token" : "API token"}</Label>
            <Input id="apify-token" type="password" autoComplete="off" placeholder="apify_api_…" value={token} aria-invalid={fieldError ? true : undefined} onChange={(e) => { setToken(e.target.value); setFieldError(null); }} />
            {fieldError && <FieldNote error>{fieldError}</FieldNote>}
          </div>
        ) : (
          <div className="flex items-center justify-between gap-3 rounded-xl bg-white/70 px-4 py-2.5 ring-1 ring-black/[0.06]">
            <span className="text-sm text-muted-foreground">
              Token <span className="font-mono text-foreground">{view.masked}</span>
            </span>
            <button type="button" onClick={() => setReplacing(true)} className="text-sm text-primary underline-offset-4 hover:underline">
              Replace
            </button>
          </div>
        )}

        <div className="flex flex-wrap items-center gap-3">
          {showInput ? (
            <>
              <Button onClick={save} disabled={busy}>
                Save &amp; test
              </Button>
              {replacing && (
                <Button variant="ghost" onClick={() => { setReplacing(false); setToken(""); setFieldError(null); }}>
                  Cancel
                </Button>
              )}
            </>
          ) : (
            <Button variant="outline" onClick={test} disabled={busy}>
              Test connection
            </Button>
          )}
          {view.source === "ui" && !replacing && (
            <Button variant="ghost" onClick={remove} disabled={busy}>
              Remove saved token
            </Button>
          )}
        </div>
        {error && (
          <p className="text-sm text-destructive" role="alert">
            {error}
          </p>
        )}
      </CardContent>
    </Card>
  );
}
