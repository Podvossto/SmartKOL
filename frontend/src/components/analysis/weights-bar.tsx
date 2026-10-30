"use client";

import { ChevronDown } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { Collapse } from "@/components/ui/collapse";
import type { Axis, Weights } from "@/lib/analysis-api";
import { cn } from "@/lib/utils";

export const AXIS_LABELS: Record<Axis, { name: string; hint: string }> = {
  relevance: { name: "Fit with the brand", hint: "How well the creator's category, style and products match the brand. Judged by the AI; brand safety can cap it." },
  engagement: { name: "Engagement", hint: "Likes, comments and shares per view, and views per follower, compared with creators of the same size in this search. Computed from their latest videos." },
  audience: { name: "Audience fit (estimated)", hint: "Whether the creator's audience looks like the brand's target. The AI's estimate from their content: TikTok does not show who watches." },
  activity: { name: "Activity", hint: "How often they post, how recently, how many videos are ads, and how steady their views are. Computed from their latest videos." },
};
const AXES = Object.keys(AXIS_LABELS) as Axis[];
export const DEFAULT_WEIGHTS: Weights = { relevance: 40, engagement: 25, audience: 20, activity: 15 };
const SAVE_AFTER_MS = 500;

/** How much each axis counts in the total. Moving a slider re-ranks the list at once; nothing is re-read or re-scored. */
export function WeightsBar({ weights, onChange }: { weights: Weights; onChange: (w: Weights) => void }) {
  const [open, setOpen] = useState(false);
  const [raw, setRaw] = useState<Weights>(weights);
  const timer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);
  const sum = AXES.reduce((n, a) => n + raw[a], 0);
  const percent = (a: Axis) => (sum > 0 ? Math.round((raw[a] / sum) * 100) : 0);

  useEffect(() => () => clearTimeout(timer.current), []);

  const set = (next: Weights) => {
    setRaw(next);
    clearTimeout(timer.current);
    if (AXES.some((a) => next[a] > 0)) timer.current = setTimeout(() => onChange(next), SAVE_AFTER_MS);
  };

  return (
    <div className="flex flex-col rounded-2xl bg-white/70 px-4 py-2.5 ring-1 ring-black/[0.05]">
      <button type="button" aria-expanded={open} aria-controls="score-weights" onClick={() => setOpen(!open)} className="flex flex-wrap items-center justify-between gap-2 text-left text-sm">
        <span className="font-medium">Score weights</span>
        <span className="flex items-center gap-1.5 text-muted-foreground">
          {AXES.map((a) => `${AXIS_LABELS[a].name.split(" ")[0]} ${percent(a)}%`).join(" · ")}
          <ChevronDown className={cn("size-4 transition-transform duration-300", open && "rotate-180")} strokeWidth={1.75} />
        </span>
      </button>
      <Collapse open={open} id="score-weights">
        <div className="flex flex-col gap-3 pb-2 pt-4">
          <p className="text-sm text-muted-foreground">Decide what matters most for this brand. The total is the weighted average of the four scores, so the ranking changes as you move a slider.</p>
          <ul className="grid gap-x-8 gap-y-3 sm:grid-cols-2">
            {AXES.map((a) => (
              <li key={a} className="flex flex-col gap-1">
                <label htmlFor={`weight-${a}`} title={AXIS_LABELS[a].hint} className="flex items-center justify-between text-sm">
                  {AXIS_LABELS[a].name}
                  <span className="tabular-nums text-muted-foreground">{percent(a)}%</span>
                </label>
                <input id={`weight-${a}`} type="range" min={0} max={100} step={5} value={raw[a]} onChange={(e) => set({ ...raw, [a]: Number(e.target.value) })} className="w-full accent-primary" />
              </li>
            ))}
          </ul>
          {sum === 0 && (
            <p className="text-sm text-destructive" role="alert">
              Give at least one score some weight.
            </p>
          )}
          <button type="button" onClick={() => set(DEFAULT_WEIGHTS)} className="w-fit text-sm text-primary underline-offset-4 hover:underline">
            Back to the suggested weights (40 / 25 / 20 / 15)
          </button>
        </div>
      </Collapse>
    </div>
  );
}
