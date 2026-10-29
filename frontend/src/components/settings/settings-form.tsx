"use client";

import { useEffect, useState } from "react";

import { type SettingsView, settingsApi } from "@/lib/settings-api";

import { ApifyCard } from "./apify-card";
import { LlmCard } from "./llm-card";
import { errorMessage } from "./shared";

export function SettingsForm() {
  const [view, setView] = useState<SettingsView | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    settingsApi.get().then(setView).catch((err) => setError(errorMessage(err)));
  }, []);

  if (error) return <p className="text-destructive">Could not load settings: {error}</p>;
  if (!view) return <p className="text-muted-foreground">Loading…</p>;

  return (
    <div className="flex flex-col gap-6">
      <ApifyCard view={view.apify} onChange={setView} />
      <LlmCard view={view} onChange={setView} />
    </div>
  );
}
