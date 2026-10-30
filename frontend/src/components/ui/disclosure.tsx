"use client";

import { ChevronDown } from "lucide-react";
import { useId, useState } from "react";

import { cn } from "@/lib/utils";

import { Collapse } from "./collapse";

/** Collapsed-by-default section: keeps a page short while leaving the detail one click away. */
export function Disclosure({ title, hint, badge, defaultOpen = false, children }: { title: string; hint?: string; badge?: React.ReactNode; defaultOpen?: boolean; children: React.ReactNode }) {
  const [open, setOpen] = useState(defaultOpen);
  const panelId = useId();
  return (
    <section className="rounded-3xl bg-white/70 ring-1 ring-black/[0.05]">
      <button
        type="button"
        aria-expanded={open}
        aria-controls={panelId}
        onClick={() => setOpen(!open)}
        className="flex w-full items-center justify-between gap-4 rounded-3xl px-6 py-4 text-left transition-colors hover:bg-white"
      >
        <span className="flex flex-wrap items-baseline gap-x-3">
          <span className="font-medium">{title}</span>
          {badge}
          {hint && <span className="text-sm text-muted-foreground">{hint}</span>}
        </span>
        <ChevronDown className={cn("size-4 shrink-0 text-muted-foreground transition-transform duration-500 ease-[cubic-bezier(0.32,0.72,0,1)]", open && "rotate-180")} strokeWidth={1.75} />
      </button>
      <Collapse open={open} id={panelId}>
        <div className="flex flex-col gap-5 px-6 pb-6">{children}</div>
      </Collapse>
    </section>
  );
}
