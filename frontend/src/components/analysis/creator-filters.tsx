"use client";

import { Check } from "lucide-react";

import type { CreatorFilters } from "@/lib/analysis-api";
import { cn } from "@/lib/utils";

const SIZES: { name: string; range: string; min: number; max: number }[] = [
  { name: "Any size", range: "", min: 0, max: 0 },
  { name: "10K+", range: "", min: 10_000, max: 0 },
  { name: "Nano", range: "under 10K", min: 0, max: 10_000 },
  { name: "Micro", range: "10K–100K", min: 10_000, max: 100_000 },
  { name: "Mid", range: "100K–500K", min: 100_000, max: 500_000 },
  { name: "Macro", range: "500K–1M", min: 500_000, max: 1_000_000 },
  { name: "Mega", range: "1M+", min: 1_000_000, max: 0 },
];

// Recency is off by default: a hashtag search shows one video per creator, so "last post" would be wrong for most of them.
export const DEFAULT_FILTERS: CreatorFilters = { thai_min: 60, skip_private: true, max_age_days: 0, min_followers: 10_000, max_followers: 0, skip_shops: true };

type Dropped = Record<"thai" | "private" | "recent" | "shops", number> | undefined;

/** A filter you switch on and off. When on it says how many creators it removes. */
function Switch({ on, onChange, label, hint, removes }: { on: boolean; onChange: (on: boolean) => void; label: string; hint: string; removes?: number }) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={on}
      title={hint}
      onClick={() => onChange(!on)}
      className={cn("flex items-center gap-1.5 rounded-full py-1 pl-2 pr-3 text-sm ring-1 transition-all duration-300", on ? "bg-primary/[0.07] text-foreground ring-primary/30" : "bg-white text-muted-foreground ring-black/10 hover:text-foreground")}
    >
      <span className={cn("grid size-4 place-items-center rounded-full transition-colors", on ? "bg-primary text-primary-foreground" : "ring-1 ring-black/20")}>{on && <Check className="size-3" strokeWidth={3} />}</span>
      {label}
      {on && removes != null && removes > 0 && <span className="text-xs text-muted-foreground">−{removes}</span>}
    </button>
  );
}

/** The hard filters, in one compact bar. They re-read the stored list, so changing them never costs anything. */
export function CreatorFilterPanel({ filters, onChange, dropped }: { filters: CreatorFilters; onChange: (change: Partial<CreatorFilters>) => void; dropped: Dropped }) {
  const size = SIZES.findIndex((s) => s.min === filters.min_followers && s.max === filters.max_followers);
  return (
    <div className="flex flex-wrap items-center gap-x-2 gap-y-2 rounded-2xl bg-white/70 px-3 py-2.5 ring-1 ring-black/[0.05]">
      <Switch on={filters.thai_min > 0} onChange={(on) => onChange({ thai_min: on ? 60 : 0 })} label="Thai" hint="At least 60% of the captions found are Thai." removes={dropped?.thai} />
      <Switch on={filters.skip_shops} onChange={(on) => onChange({ skip_shops: on })} label="Creators only" hint="Leaves out shops, brands and media pages, competitors included. The AI sorts each account from its bio and captions, so check the odd one." removes={dropped?.shops} />
      <Switch on={filters.skip_private} onChange={(on) => onChange({ skip_private: on })} label="Public" hint="Leave out private accounts." removes={dropped?.private} />
      <Switch on={filters.max_age_days > 0} onChange={(on) => onChange({ max_age_days: on ? 30 : 0 })} label="Last 30 days" hint="Posted in the last 30 days. Judged from the one video found, so it can wrongly drop active creators." removes={dropped?.recent} />
      <span aria-hidden className="mx-1 hidden h-5 w-px bg-black/10 sm:block" />
      <div role="group" aria-label="Account size" className="flex flex-wrap gap-1">
        {SIZES.map((s, i) => (
          <button
            key={s.name}
            type="button"
            aria-pressed={size === i}
            title={s.range || undefined}
            onClick={() => onChange({ min_followers: s.min, max_followers: s.max })}
            className={cn("rounded-full px-2.5 py-1 text-xs transition-all duration-300", size === i ? "bg-primary text-primary-foreground shadow-sm" : "bg-muted text-muted-foreground hover:text-foreground")}
          >
            {s.name}
          </button>
        ))}
      </div>
    </div>
  );
}
