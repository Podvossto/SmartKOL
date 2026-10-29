"use client";

import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { type ApifyAccount, type SettingsView, settingsApi } from "@/lib/settings-api";

import { SourceBadge, errorMessage, usd } from "./shared";

export function ApifyCard({ view, onChange }: { view: SettingsView["apify"]; onChange: (v: SettingsView) => void }) {
  const [token, setToken] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [account, setAccount] = useState<ApifyAccount | null>(null);

  async function saveAndTest() {
    setBusy(true);
    setError(null);
    setAccount(null);
    try {
      if (token.trim()) {
        onChange(await settingsApi.saveApify(token));
        setToken("");
      }
      setAccount(await settingsApi.testApify());
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  async function removeSaved() {
    setBusy(true);
    setError(null);
    setAccount(null);
    try {
      onChange(await settingsApi.clearApify());
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-3">
          Apify <SourceBadge source={view.source} />
        </CardTitle>
        <CardDescription>
          Collects Facebook page and TikTok creator data.{" "}
          <a
            className="text-primary underline-offset-4 hover:underline"
            href="https://console.apify.com/settings/integrations"
            target="_blank"
            rel="noreferrer"
          >
            Get your API token
          </a>
          . Every run is billed to this account.
        </CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        <div className="flex flex-col gap-2">
          <Label htmlFor="apify-token">API token {view.masked && <span className="text-muted-foreground">(current {view.masked})</span>}</Label>
          <Input
            id="apify-token"
            type="password"
            autoComplete="off"
            placeholder={view.configured ? "Leave blank to keep the current token" : "apify_api_…"}
            value={token}
            onChange={(e) => setToken(e.target.value)}
          />
        </div>
        <div className="flex flex-wrap items-center gap-3">
          <Button onClick={saveAndTest} disabled={busy || (!view.configured && !token.trim())}>
            {token.trim() ? "Save & test" : "Test connection"}
          </Button>
          {view.source === "ui" && (
            <Button variant="outline" onClick={removeSaved} disabled={busy}>
              Remove saved token
            </Button>
          )}
        </div>
        {account && (
          <p className="text-sm" role="status">
            Connected as <strong>{account.username}</strong> · {account.plan} plan · {usd(account.remaining_usd)} left of{" "}
            {usd(account.limit_usd)} this month
            {account.cycle_end && ` (resets ${new Date(account.cycle_end).toLocaleDateString("en-GB", { day: "numeric", month: "short" })})`}
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
