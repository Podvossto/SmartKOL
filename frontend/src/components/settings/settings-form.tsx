"use client";

import { useEffect, useState } from "react";

import { type SettingsView, settingsApi } from "@/lib/settings-api";
import { cn } from "@/lib/utils";

import { ApifyCard } from "./apify-card";
import { LlmCard } from "./llm-card";
import { PromptsTab } from "./prompts-tab";
import { errorMessage } from "./shared";

const TABS = [
  { id: "connections", label: "Connections" },
  { id: "ai", label: "AI instructions" },
] as const;
type Tab = (typeof TABS)[number]["id"];

export function SettingsForm() {
  const [view, setView] = useState<SettingsView | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [tab, setTab] = useState<Tab>("connections");

  useEffect(() => {
    settingsApi.get().then(setView).catch((err) => setError(errorMessage(err)));
  }, []);

  if (error) return <p className="text-destructive">Could not load settings: {error}</p>;
  if (!view) return <p className="text-muted-foreground">Loading…</p>;

  return (
    <div className="flex flex-col gap-6">
      <div role="tablist" aria-label="Settings" className="flex w-fit gap-1 rounded-full bg-muted p-1">
        {TABS.map((t) => (
          <button
            key={t.id}
            role="tab"
            id={`tab-${t.id}`}
            aria-selected={tab === t.id}
            aria-controls={`panel-${t.id}`}
            type="button"
            onClick={() => setTab(t.id)}
            className={cn("rounded-full px-4 py-1.5 text-sm transition-all duration-300", tab === t.id ? "bg-white font-medium shadow-sm" : "text-muted-foreground hover:text-foreground")}
          >
            {t.label}
          </button>
        ))}
      </div>
      <div role="tabpanel" id={`panel-${tab}`} aria-labelledby={`tab-${tab}`} className="flex flex-col gap-6">
        {tab === "connections" ? (
          <>
            <ApifyCard view={view.apify} onChange={setView} />
            <LlmCard view={view} onChange={setView} />
          </>
        ) : (
          <PromptsTab />
        )}
      </div>
    </div>
  );
}
