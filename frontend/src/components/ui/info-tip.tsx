"use client";

import { Info } from "lucide-react";
import { useId } from "react";

/** A small "i" that shows its detail on hover or keyboard focus, for facts that matter but shouldn't take up room. */
export function InfoTip({ label, text, children }: { label: string; text?: string; children: React.ReactNode }) {
  const id = useId();
  return (
    <span className="group relative inline-flex">
      <button type="button" aria-label={label} aria-describedby={id} className="flex items-center gap-1 rounded-full p-1.5 text-muted-foreground/70 transition-colors hover:text-foreground focus-visible:text-foreground focus-visible:outline-2 focus-visible:outline-ring">
        <Info className="size-3.5" strokeWidth={1.75} />
        {text && <span className="text-xs">{text}</span>}
      </button>
      <span
        id={id}
        role="tooltip"
        className="pointer-events-none absolute right-0 top-full z-30 mt-1 flex w-64 translate-y-1 flex-col gap-1.5 rounded-2xl bg-foreground px-4 py-3 text-xs leading-relaxed text-background opacity-0 shadow-[0_16px_40px_-12px_rgba(10,20,60,0.45)] transition-all duration-300 ease-[cubic-bezier(0.32,0.72,0,1)] group-focus-within:translate-y-0 group-focus-within:opacity-100 group-hover:translate-y-0 group-hover:opacity-100"
      >
        {children}
      </span>
    </span>
  );
}
