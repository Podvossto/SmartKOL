import { Check } from "lucide-react";
import Link from "next/link";

import type { Analysis } from "@/lib/analysis-api";
import { type StepKey, STEPS } from "@/lib/steps";
import { cn } from "@/lib/utils";

/**
 * The workflow as a progress track: equal-width steps, a numbered dot on a line, its name underneath. Finished steps
 * are links, the current one is marked, later ones wait. Not a pill, so it never echoes the menu above it.
 */
export function WizardStepper({ analysis, active }: { analysis: Analysis; active: StepKey }) {
  const activeIndex = STEPS.findIndex((s) => s.key === active);
  return (
    <nav aria-label="Steps">
      <ol className="flex">
        {STEPS.map((step, i) => {
          const done = i < activeIndex;
          const current = step.key === active;
          const open = !current && step.ready(analysis);
          const body = (
            <>
              <span
                className={cn(
                  "relative z-10 grid size-6 place-items-center rounded-full text-[11px] font-medium transition-colors duration-500",
                  done ? "bg-primary text-primary-foreground" : current ? "bg-background text-primary ring-2 ring-primary" : "bg-background text-muted-foreground/70 ring-1 ring-black/15",
                )}
              >
                {done ? <Check className="size-3" strokeWidth={3} /> : i + 1}
              </span>
              <span className={cn("text-xs", current ? "font-medium text-foreground" : open || done ? "text-muted-foreground" : "text-muted-foreground/60")}>{step.label}</span>
            </>
          );
          const cls = "flex flex-col items-center gap-1.5 rounded-md";
          return (
            <li key={step.key} aria-current={current ? "step" : undefined} className="relative w-[72px] sm:w-20">
              {i < STEPS.length - 1 && <span aria-hidden className={cn("absolute left-1/2 top-3 h-px w-full -translate-y-1/2 transition-colors duration-500", done ? "bg-primary" : "bg-black/15")} />}
              {open ? (
                <Link href={step.href(analysis.id)} className={cn(cls, "transition-opacity hover:opacity-70")}>
                  {body}
                </Link>
              ) : (
                <span className={cls}>{body}</span>
              )}
            </li>
          );
        })}
      </ol>
    </nav>
  );
}
