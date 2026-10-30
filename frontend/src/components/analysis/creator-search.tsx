"use client";

import { Loader2 } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";

import { PlatformIcon } from "@/components/platform-icon";
import { PillButton } from "@/components/ui/pill-button";
import { type CreatorEstimate, type Preset, type Profile, analysisApi } from "@/lib/analysis-api";
import { errorMessage } from "@/lib/errors";
import { usd } from "@/lib/format";
import { STEPS } from "@/lib/steps";
import { cn } from "@/lib/utils";

import { useCurrentAnalysis } from "./context";

const BUDGETS: { id: Preset; name: string; text: string }[] = [
  { id: "lean", name: "Lean", text: "A quick look: your first 3 hashtags, 25 videos each." },
  { id: "full", name: "Full", text: "A wider net: your first 6 hashtags, 40 videos each. More creators to choose from." },
];

function Budget({ preset, active, onPick, estimate }: { preset: (typeof BUDGETS)[number]; active: boolean; onPick: () => void; estimate: CreatorEstimate["estimate"] | undefined }) {
  return (
    <button
      type="button"
      aria-pressed={active}
      onClick={onPick}
      className={cn(
        "flex flex-1 flex-col gap-1 rounded-2xl p-4 text-left ring-1 transition-all duration-300 hover:-translate-y-0.5",
        active ? "bg-primary/[0.06] ring-2 ring-primary" : "bg-white/70 ring-black/[0.08] hover:ring-black/20",
      )}
    >
      <span className="flex items-baseline justify-between gap-3">
        <span className="font-medium">{preset.name}</span>
        <span className="font-mono text-sm tabular-nums">{estimate ? (estimate.cached ? "$0 · saved" : `≈ ${usd(estimate.usd)}`) : "…"}</span>
      </span>
      <span className="text-sm text-muted-foreground">{preset.text}</span>
      {estimate && estimate.hashtags.length > 0 && (
        <span className="text-xs text-muted-foreground">
          Reads about {estimate.videos} videos from {estimate.hashtags.length} hashtag{estimate.hashtags.length === 1 ? "" : "s"}
        </span>
      )}
    </button>
  );
}

function Running({ hashtags, phase }: { hashtags: number; phase: "searching" | "sorting" | null }) {
  const [seconds, setSeconds] = useState(0);
  useEffect(() => {
    const timer = setInterval(() => setSeconds((s) => s + 1), 1000);
    return () => clearInterval(timer);
  }, []);
  return (
    <div className="flex items-center gap-4" role="status">
      <Loader2 className="size-5 animate-spin text-primary" strokeWidth={1.75} />
      <div>
        <p className="font-medium">{phase === "sorting" ? "Telling creators from shops…" : "Searching TikTok…"}</p>
        <p className="text-sm text-muted-foreground">
          {phase === "sorting"
            ? "The AI reads each account's bio and captions, so competitors and shops can be set aside. About half a minute."
            : `Reading the latest videos under ${hashtags} hashtag${hashtags === 1 ? "" : "s"}. Usually under a minute.`}{" "}
          You can leave this page; the search keeps running.
        </p>
      </div>
      <span className="ml-auto font-mono text-sm tabular-nums text-muted-foreground" aria-hidden>
        {seconds}s
      </span>
    </div>
  );
}

/** Pick how wide the search is, see the price, run it. Nothing is spent before the button is pressed. */
export function CreatorSearch() {
  const { analysis, adopt } = useCurrentAnalysis();
  const profile = analysis.profile as Profile;
  const [preset, setPreset] = useState<Preset>("lean");
  const [estimates, setEstimates] = useState<{ key: string; byPreset: Partial<Record<Preset, CreatorEstimate["estimate"]>>; left: number | null } | null>(null);
  const [starting, setStarting] = useState(false);
  const router = useRouter();
  const started = useRef(false); // only a search started on this page opens the list; arriving at a finished one does not
  const [error, setError] = useState<string | null>(null);
  const key = JSON.stringify([profile.tiktok.hashtags_th, profile.tiktok.hashtags_en, analysis.creators.status]);
  const running = analysis.creators.status === "running";

  useEffect(() => {
    let live = true;
    Promise.all(BUDGETS.map((b) => analysisApi.creatorsEstimate(analysis.id, b.id)))
      .then(([lean, full]) => live && setEstimates({ key, byPreset: { lean: lean.estimate, full: full.estimate }, left: lean.account?.remaining_usd ?? null }))
      .catch((err) => live && setError(errorMessage(err)));
    return () => {
      live = false;
    };
  }, [analysis.id, key]);

  const { status, found } = analysis.creators;
  useEffect(() => {
    if (started.current && status === "done" && found > 0) {
      started.current = false;
      router.push(STEPS.find((s) => s.key === "creators")!.href(analysis.id));
    }
  }, [status, found, router, analysis.id]);

  const fresh = estimates?.key === key ? estimates : null;
  const chosen = fresh?.byPreset[preset];
  const tooPricey = !!chosen && fresh?.left != null && chosen.usd > fresh.left;
  const noTags = !!chosen && chosen.hashtags.length === 0;
  const done = analysis.creators.status === "done";

  async function search() {
    setStarting(true);
    setError(null);
    started.current = true;
    try {
      adopt(await analysisApi.searchCreators(analysis.id, preset));
    } catch (err) {
      started.current = false;
      setError(errorMessage(err));
    } finally {
      setStarting(false);
    }
  }

  return (
    <div className="flex flex-col gap-5 rounded-3xl bg-white/70 px-6 py-5 ring-1 ring-black/[0.05]">
      <p className="flex items-center gap-2 font-medium">
        <PlatformIcon platform="tiktok" /> Search TikTok
      </p>
      {running ? (
        <Running hashtags={analysis.creators.hashtags.length || chosen?.hashtags.length || 0} phase={analysis.creators.phase} />
      ) : (
        <>
          <div role="group" aria-label="Search budget" className="flex flex-col gap-3 sm:flex-row">
            {BUDGETS.map((b) => (
              <Budget key={b.id} preset={b} active={preset === b.id} onPick={() => setPreset(b.id)} estimate={fresh?.byPreset[b.id]} />
            ))}
          </div>
          <div className="flex flex-wrap items-center justify-between gap-4">
            <p className="text-sm text-muted-foreground" aria-live="polite">
              {noTags && "Add at least one hashtag above to search."}
              {status === "done" && found === 0 && "That search found no one. Try the Full budget or other hashtags."}
              {tooPricey && `Needs about ${usd(chosen!.usd)} but only ${usd(fresh!.left!)} of Apify credit is left.`}
              {!noTags && !tooPricey && chosen && (chosen.cached ? "You searched this before. Showing it again costs nothing." : `Estimated cost ${usd(chosen.usd)}${fresh?.left != null ? ` of ${usd(fresh.left)} Apify credit left` : ""}. Nothing is spent until you press search.`)}
            </p>
            <PillButton onClick={search} loading={starting} disabled={!chosen || noTags || tooPricey}>
              {done ? "Search again" : "Search creators"}
            </PillButton>
          </div>
        </>
      )}
      {(error || analysis.creators.status === "error") && (
        <p className="text-sm text-destructive" role="alert">
          {error ?? analysis.creators.error}
        </p>
      )}
    </div>
  );
}
