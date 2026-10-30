"use client";

import { ChevronDown, Trash2 } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";

import { BrandLogo } from "@/components/brand-logo";
import { Button } from "@/components/ui/button";
import { Collapse } from "@/components/ui/collapse";
import { type RecentItem, analysisApi } from "@/lib/analysis-api";
import { timeAgo } from "@/lib/format";

const VISIBLE = 3;
const NEEDS_ATTENTION = { running: "In progress", profiling: "In progress", awaiting_facebook: "Needs your input", error: "Failed", done: "" } as const;
/** Absolute start time, e.g. "30 Oct, 14:05", so analyses of the same brand can be told apart. */
const startedAt = new Intl.DateTimeFormat("en-GB", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit", hour12: false });

/** Past analyses: reopening one is free (everything is cached), and each can be deleted for good. */
export function RecentList() {
  const [items, setItems] = useState<RecentItem[] | null>(null);
  const [confirming, setConfirming] = useState<string | null>(null);
  const [all, setAll] = useState(false);
  const [leaving, setLeaving] = useState<string[]>([]);

  useEffect(() => {
    analysisApi.recent().then(setItems).catch(() => setItems([]));
  }, []);

  async function remove(id: string) {
    setConfirming(null);
    setLeaving((current) => [...current, id]); // the row folds away first, then it is dropped from the list
    await analysisApi.remove(id).catch(() => null);
    setTimeout(() => setItems((current) => current?.filter((item) => item.id !== id) ?? null), 480);
  }

  const row = (item: RecentItem) => {
    const note = NEEDS_ATTENTION[item.status];
    const meta = [item.website, item.facebook && `facebook/${item.facebook}`, note, timeAgo(item.created_at)].filter(Boolean).join(" · ");
    return (
      <li key={item.id}>
       <Collapse open={!leaving.includes(item.id)}>
        <div className="p-0.5 pb-2">
        <div className="flex items-center gap-2 rounded-2xl bg-white/70 p-2 pr-3 ring-1 ring-black/[0.05] transition-all duration-500 hover:-translate-y-px hover:bg-white hover:shadow-[0_8px_24px_-12px_rgba(20,40,120,0.3)]">
        <Link href={`/analysis/${item.id}`} className="flex min-w-0 flex-1 items-center gap-3 rounded-xl">
          <BrandLogo id={item.id} hasLogo={item.has_logo} name={item.title} className="size-10 text-base" />
          <span className="min-w-0">
            <span className="flex items-baseline gap-2">
              <span className="min-w-0 truncate font-medium">{item.title}</span>
              <time dateTime={item.created_at} className="shrink-0 text-xs tabular-nums text-muted-foreground">{startedAt.format(new Date(item.created_at))}</time>
            </span>
            <span className="block truncate text-xs text-muted-foreground">{meta}</span>
          </span>
        </Link>
        {confirming === item.id ? (
          <span className="flex items-center gap-1">
            <Button size="sm" variant="destructive" onClick={() => remove(item.id)}>
              Delete
            </Button>
            <Button size="sm" variant="ghost" onClick={() => setConfirming(null)}>
              Keep
            </Button>
          </span>
        ) : (
          <button
            type="button"
            aria-label={`Delete ${item.title}`}
            onClick={() => setConfirming(item.id)}
            className="rounded-full p-2 text-muted-foreground/60 transition-colors hover:bg-black/[0.05] hover:text-destructive"
          >
            <Trash2 className="size-4" strokeWidth={1.5} />
          </button>
        )}
        </div>
        </div>
       </Collapse>
      </li>
    );
  };

  if (!items?.length) return null;
  return (
    <section aria-labelledby="recent" className="flex flex-col gap-3">
      <h2 id="recent" className="text-sm font-medium text-muted-foreground">
        Recent
      </h2>
      <ul className="flex flex-col">{items.slice(0, VISIBLE).map(row)}</ul>
      {items.length > VISIBLE && (
        <>
          <Collapse open={all}>
            <ul className="flex flex-col">{items.slice(VISIBLE).map(row)}</ul>
          </Collapse>
          <button type="button" aria-expanded={all} onClick={() => setAll(!all)} className="flex w-fit items-center gap-1.5 px-1 text-sm text-muted-foreground transition-colors hover:text-foreground">
            {all ? "Show fewer" : `Show all ${items.length}`}
            <ChevronDown className={`size-3.5 transition-transform duration-500 ease-[cubic-bezier(0.32,0.72,0,1)] ${all ? "rotate-180" : ""}`} strokeWidth={1.75} />
          </button>
        </>
      )}
    </section>
  );
}
