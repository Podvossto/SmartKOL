"use client";

import { Check, X } from "lucide-react";
import { useEffect, useState } from "react";

import { Card } from "@/components/ui/card";
import type { Step } from "@/lib/analysis-api";
import { cn } from "@/lib/utils";

function Node({ state }: { state: Step["state"] }) {
  const base = "relative grid size-8 shrink-0 place-items-center rounded-full";
  if (state === "done") return <span className={cn(base, "bg-primary text-primary-foreground")}><Check className="size-4" strokeWidth={2.5} /></span>;
  if (state === "error") return <span className={cn(base, "bg-destructive text-white")}><X className="size-4" strokeWidth={2.5} /></span>;
  if (state === "running") {
    return (
      <span className={cn(base, "bg-primary/10")}>
        <span className="absolute inset-0 animate-ping rounded-full bg-primary/20" />
        <span className="size-2.5 rounded-full bg-primary" />
      </span>
    );
  }
  if (state === "skipped") return <span className={cn(base, "bg-muted text-muted-foreground")}>–</span>;
  return <span className={cn(base, "border border-dashed border-border bg-white")} />;
}

/** "20–60 seconds", or "1–2 minutes" once the range reaches a minute. */
function waitText([low, high]: [number, number]): string {
  return high >= 90 ? `${Math.round(low / 60) || 1}–${Math.round(high / 60)} minutes` : `${low}–${high} seconds`;
}

export function ProgressSteps({ title, steps, eta, onCancel }: { title: string; steps: Step[]; eta?: [number, number] | null; onCancel?: () => void }) {
  const [seconds, setSeconds] = useState(0);
  useEffect(() => {
    const timer = setInterval(() => setSeconds((s) => s + 1), 1000);
    return () => clearInterval(timer);
  }, []);

  return (
    <Card className="animate-rise [--card-spacing:--spacing(7)]">
      <div className="flex flex-col gap-7 px-(--card-spacing)">
        <div className="flex items-baseline justify-between gap-4">
          <h2 className="font-heading text-xl font-semibold tracking-tight">{title}</h2>
          <span className="font-mono text-sm tabular-nums text-muted-foreground" aria-hidden>
            {seconds}s
          </span>
        </div>
        {eta && <p className="-mt-4 text-sm text-muted-foreground">Usually takes {waitText(eta)}. You can leave this page; the analysis keeps running.</p>}
        <ol className="flex flex-col" aria-live="polite">
          {steps.map((step, i) => (
            <li key={step.key} className="relative flex items-start gap-4 pb-6 last:pb-0">
              {i < steps.length - 1 && <span aria-hidden className={cn("absolute left-4 top-8 h-[calc(100%-2rem)] w-px", step.state === "done" ? "bg-primary/40" : "bg-border")} />}
              <Node state={step.state} />
              <div className="pt-1">
                <p className={cn("text-[15px]", step.state === "pending" ? "text-muted-foreground" : "font-medium")}>{step.label}</p>
                {step.detail && <p className="text-sm text-muted-foreground">{step.detail}</p>}
              </div>
            </li>
          ))}
        </ol>
        {onCancel && (
          <button type="button" onClick={onCancel} className="w-fit rounded-full px-4 py-2 text-sm text-muted-foreground transition-all duration-300 hover:bg-destructive/10 hover:text-destructive">
            Cancel analysis
          </button>
        )}
      </div>
    </Card>
  );
}
