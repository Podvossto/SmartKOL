import { Database, Sparkles } from "lucide-react";

import { cn } from "@/lib/utils";

const KINDS = {
  data: { icon: Database, label: "From source", tone: "text-muted-foreground" },
  ai: { icon: Sparkles, label: "AI-generated", tone: "text-primary" },
} as const;

/** Where a piece of information comes from: read from a source, or written by the model. Quiet text; detail on hover. */
export function Origin({ kind, model, className }: { kind: keyof typeof KINDS; model?: string | null; className?: string }) {
  const { icon: Icon, label, tone } = KINDS[kind];
  const tip =
    kind === "ai"
      ? `Written by ${model ?? "the language model"} from what was read. Check it against the sources.`
      : "Taken as-is from the website or Facebook page. Not written by a model.";
  return (
    <span tabIndex={0} className={cn("group relative inline-flex cursor-default items-center gap-1 text-xs outline-none", tone, className)}>
      <Icon className="size-3" strokeWidth={1.75} />
      {label}
      <span
        role="tooltip"
        className="pointer-events-none absolute left-0 top-full z-30 mt-1.5 w-44 translate-y-1 sm:w-52 rounded-2xl bg-foreground px-3.5 py-2.5 text-xs font-normal leading-relaxed text-background opacity-0 shadow-[0_16px_40px_-12px_rgba(10,20,60,0.45)] transition-all duration-300 ease-[cubic-bezier(0.32,0.72,0,1)] group-hover:translate-y-0 group-hover:opacity-100 group-focus:translate-y-0 group-focus:opacity-100"
      >
        {tip}
      </span>
    </span>
  );
}
