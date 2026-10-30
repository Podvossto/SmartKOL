import type { Creator } from "@/lib/analysis-api";

import { Origin } from "./origin";
import { Eyebrow } from "./panel";
import { ScoreCell } from "./score-cell";
import { AXIS_LABELS } from "./weights-bar";

const RUBRIC = [
  ["category", "Category"],
  ["style", "Style"],
  ["product", "Products"],
  ["safety", "Brand safety"],
] as const;

function Axis({ title, hint, value, estimated, ai, model, children }: { title: string; hint: string; value: number; estimated?: boolean; ai?: boolean; model?: string | null; children: React.ReactNode }) {
  return (
    <li className="grid min-w-0 grid-cols-1 gap-3 px-5 py-5 sm:grid-cols-[11rem_minmax(0,1fr)] sm:gap-6 sm:px-6">
      <div className="flex flex-col gap-2">
        <span className="text-sm font-medium" title={hint}>
          {title}
        </span>
        <ScoreCell value={value} strong estimated={estimated} />
        {ai ? <Origin kind="ai" model={model} /> : <span className="text-xs text-muted-foreground">Computed from the videos</span>}
      </div>
      <div className="flex flex-col gap-2 text-[15px] leading-relaxed">{children}</div>
    </li>
  );
}

/** The four scores of one creator, each with why: the AI's reason, or the numbers it was computed from. */
export function CreatorScores({ creator: c }: { creator: Creator }) {
  const s = c.score;
  if (!s) return null;
  return (
    <section className="flex flex-col gap-3">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <Eyebrow>Score</Eyebrow>
        <p className="flex flex-wrap items-baseline gap-x-2 gap-y-1">
          {c.rank != null && <span className="text-sm text-muted-foreground">#{c.rank} in this list</span>}
          <span className="font-heading text-3xl font-semibold tabular-nums">{c.total}</span>
          <span className="text-sm text-muted-foreground">/ 100 with your weights</span>
        </p>
      </div>
      {s.flags.length > 0 && (
        <ul className="flex flex-col gap-1 rounded-2xl bg-amber-50 px-4 py-3 text-sm text-amber-800 ring-1 ring-amber-200" role="status">
          {s.flags.map((f) => (
            <li key={f}>{f}</li>
          ))}
        </ul>
      )}
      <ul className="divide-y divide-border rounded-3xl bg-white/80 ring-1 ring-black/[0.06]">
        <Axis title={AXIS_LABELS.relevance.name} hint={AXIS_LABELS.relevance.hint} value={s.relevance} ai model={s.model}>
          <p>{s.reason}</p>
          <p className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted-foreground">
            {RUBRIC.map(([key, label]) => (
              <span key={key}>
                {label} <b className="font-medium text-foreground">{s[key]}</b>
              </span>
            ))}
          </p>
        </Axis>
        <Axis title={AXIS_LABELS.engagement.name} hint={AXIS_LABELS.engagement.hint} value={s.engagement}>
          <p>{s.engagement_note}</p>
        </Axis>
        <Axis title={AXIS_LABELS.audience.name} hint={AXIS_LABELS.audience.hint} value={s.audience} estimated ai model={s.model}>
          <p>{s.audience_reason || "No reason given."}</p>
          <p className="text-xs text-muted-foreground">Estimated, confidence {s.confidence}. TikTok does not show who watches a creator.</p>
        </Axis>
        <Axis title={AXIS_LABELS.activity.name} hint={AXIS_LABELS.activity.hint} value={s.activity}>
          <p>{s.activity_note}</p>
        </Axis>
      </ul>
    </section>
  );
}
