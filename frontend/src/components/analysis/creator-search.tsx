"use client";

import { ChevronDown, Loader2 } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";

import { PlatformIcon } from "@/components/platform-icon";
import { Card } from "@/components/ui/card";
import { Collapse } from "@/components/ui/collapse";
import { PillButton } from "@/components/ui/pill-button";
import { type CreatorEstimate, type PlanItem, type Profile, analysisApi } from "@/lib/analysis-api";
import { errorMessage } from "@/lib/errors";
import { usd } from "@/lib/format";
import { STEPS } from "@/lib/steps";
import { cn } from "@/lib/utils";

import { useCurrentAnalysis } from "./context";
import { Eyebrow } from "./panel";

const CHOICES = [0, 10, 25, 40, 50, 100]; // videos to read per hashtag; 0 = not searched
const MAX_TOTAL = 500; // the server refuses more than this in one search
// New creators per video read, from our real test searches (64 of 75, 71 of 75 and 39 of 45 videos gave a different creator each).
const CREATORS_PER_VIDEO = 0.85;
type Counts = Record<string, number>;

// The two ready-made searches. They only fill in the numbers; the advanced list below can change every one of them.
const SHORTCUTS = [
  { key: "quick", name: "Quick look", tags: 3, videos: 25, text: "Your first 3 hashtags, 25 videos each." },
  { key: "wide", name: "Wide search", tags: 6, videos: 40, text: "Your first 6 hashtags, 40 videos each. More creators to choose from." },
] as const;

const fill = (tags: string[], count: number, videos: number): Counts => Object.fromEntries(tags.slice(0, count).map((t) => [t, videos]));
const planOf = (tags: string[], counts: Counts): PlanItem[] => tags.map((t) => ({ hashtag: t, videos: counts[t] ?? 0 })).filter((p) => p.videos > 0);
const byTag = (a: PlanItem, b: PlanItem) => a.hashtag.localeCompare(b.hashtag);
const sameCounts = (a: PlanItem[], b: PlanItem[]) => JSON.stringify([...a].sort(byTag)) === JSON.stringify([...b].sort(byTag)); // the order of the hashtags does not matter
const aboutCreators = (videos: number) => Math.max(5, Math.round((videos * CREATORS_PER_VIDEO) / 5) * 5);
type Estimates = { key: string; current?: CreatorEstimate; quick?: CreatorEstimate; wide?: CreatorEstimate };

function Option({ name, text, active, price, videos, onPick }: { name: string; text: string; active: boolean; price?: CreatorEstimate["estimate"]; videos: number; onPick: () => void }) {
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
        <span className="font-medium">{name}</span>
        <span className={cn("font-mono text-sm tabular-nums", price?.cached && "font-medium text-primary")}>{price ? (price.cached ? "Free" : `≈ ${usd(price.usd)}`) : "…"}</span>
      </span>
      <span className="text-sm text-muted-foreground">{text}</span>
      <span className="text-xs text-muted-foreground" title="An estimate from our test searches: about 0.85 different creators per video read. The real number depends on the hashtags.">
        {videos} videos · about {aboutCreators(videos)} creators
        {price?.cached && ` · you ran this before (would cost about ${usd(price.list_usd)})`}
      </span>
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

/** Pick a ready-made search, or open the advanced list and choose hashtags and video counts yourself. The price follows the choice; nothing is spent until you press search. */
export function CreatorSearch() {
  const { analysis, adopt } = useCurrentAnalysis();
  const profile = analysis.profile as Profile;
  const tags = [...profile.tiktok.hashtags_th, ...profile.tiktok.hashtags_en];
  const router = useRouter();
  const started = useRef(false); // only a search started on this page opens the list; arriving at a finished one does not
  const [counts, setCounts] = useState<Counts>(() => (analysis.creators.plan.length ? Object.fromEntries(analysis.creators.plan.map((p) => [p.hashtag, p.videos])) : fill(tags, 3, 25)));
  const [prices, setPrices] = useState<Estimates | null>(null);
  const [starting, setStarting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const plan = planOf(tags, counts);
  const shortcutPlans = SHORTCUTS.map((s) => planOf(tags, fill(tags, s.tags, s.videos)));
  const matching = shortcutPlans.findIndex((p) => sameCounts(p, plan));
  const custom = matching === -1;
  const [open, setOpen] = useState(custom); // a plan that is not one of the two ready-made ones starts with the list open
  const total = plan.reduce((n, p) => n + p.videos, 0);
  const { status, found } = analysis.creators;
  const key = JSON.stringify([plan, shortcutPlans, status]);
  const running = status === "running";
  const tooMany = total > MAX_TOTAL;
  const showsSaved = status === "done" && found > 0 && sameCounts(analysis.creators.plan, plan); // what is on the page is exactly the saved search

  useEffect(() => {
    let live = true;
    const ask = (p: PlanItem[]) => (p.length > 0 && p.reduce((n, x) => n + x.videos, 0) <= MAX_TOTAL ? analysisApi.creatorsEstimate(analysis.id, p) : Promise.resolve(undefined));
    Promise.all([ask(plan), ask(shortcutPlans[0]), ask(shortcutPlans[1])])
      .then(([current, quick, wide]) => live && setPrices({ key, current, quick, wide }))
      .catch((err) => live && setError(errorMessage(err)));
    return () => {
      live = false;
    };
    // the plans are rebuilt every render; `key` is what actually identifies them
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [analysis.id, key]);

  useEffect(() => {
    if (started.current && status === "done" && found > 0) {
      started.current = false;
      router.push(STEPS.find((s) => s.key === "creators")!.href(analysis.id));
    }
  }, [status, found, router, analysis.id]);

  const creatorsHref = STEPS.find((s) => s.key === "creators")!.href(analysis.id);
  const fresh = prices?.key === key ? prices : null;
  const left = fresh?.current?.account?.remaining_usd ?? null;
  const price = fresh?.current?.estimate;
  const tooPricey = !!price && left != null && price.usd > left;
  const blocked = !showsSaved && (plan.length === 0 || tooMany || tooPricey || !price);

  async function search() {
    if (showsSaved) return router.push(creatorsHref); // nothing to run: these creators are already stored
    setStarting(true);
    setError(null);
    started.current = true;
    try {
      adopt(await analysisApi.searchCreators(analysis.id, plan));
    } catch (err) {
      started.current = false;
      setError(errorMessage(err));
    } finally {
      setStarting(false);
    }
  }

  return (
    <Card>
      <section className="flex flex-col gap-5 px-(--card-spacing)">
        <div className="flex items-center gap-2">
          <PlatformIcon platform="tiktok" />
          <Eyebrow>How much to read</Eyebrow>
        </div>
        {running ? (
          <Running hashtags={analysis.creators.hashtags.length || plan.length} phase={analysis.creators.phase} />
        ) : (
          <>
            <div role="group" aria-label="Search size" className="flex flex-col gap-3 sm:flex-row">
              {SHORTCUTS.map((s, i) => (
                <Option key={s.key} name={s.name} text={s.text} active={matching === i} price={fresh?.[s.key]?.estimate} videos={shortcutPlans[i].reduce((n, p) => n + p.videos, 0)} onPick={() => setCounts(fill(tags, s.tags, s.videos))} />
              ))}
              {custom && <Option name="Your own mix" text={`${plan.length} hashtag${plan.length === 1 ? "" : "s"}, chosen below.`} active price={price} videos={total} onPick={() => setOpen(true)} />}
            </div>

            <div className="flex flex-col">
              <button type="button" aria-expanded={open} aria-controls="advanced-search" onClick={() => setOpen(!open)} className="flex w-fit items-center gap-1.5 text-sm text-primary underline-offset-4 hover:underline">
                Advanced: choose hashtags and videos yourself
                <ChevronDown className={cn("size-4 transition-transform duration-300", open && "rotate-180")} strokeWidth={1.75} />
              </button>
              <div className="-mx-2">
                <Collapse open={open} id="advanced-search">
                  <div className="flex flex-col gap-3 p-2 pt-4">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <p className="text-sm text-muted-foreground">Videos to read from each hashtag. A hashtag set to &ldquo;Don&apos;t search&rdquo; is left out.</p>
                      <button type="button" onClick={() => setCounts({})} className="rounded-full px-3 py-1 text-xs text-muted-foreground transition-colors hover:bg-muted hover:text-foreground">
                        Clear all
                      </button>
                    </div>
                    <ul className="grid gap-x-8 gap-y-1 sm:grid-cols-2">
                      {tags.map((tag) => {
                        const value = counts[tag] ?? 0;
                        return (
                          <li key={tag} className="flex items-center justify-between gap-3 rounded-xl px-2 py-1 transition-colors hover:bg-muted/50">
                            <label htmlFor={`videos-${tag}`} className={cn("min-w-0 truncate text-sm", value === 0 && "text-muted-foreground")}>
                              #{tag}
                            </label>
                            <select
                              id={`videos-${tag}`}
                              value={CHOICES.includes(value) ? value : ""}
                              onChange={(e) => setCounts((c) => ({ ...c, [tag]: Number(e.target.value) }))}
                              className={cn("rounded-full bg-white px-3 py-1 text-sm ring-1 focus-visible:outline-2 focus-visible:outline-ring", value > 0 ? "text-foreground ring-primary/40" : "text-muted-foreground ring-black/10")}
                            >
                              {!CHOICES.includes(value) && <option value="">{value} videos</option>}
                              {CHOICES.map((n) => (
                                <option key={n} value={n}>
                                  {n === 0 ? "Don't search" : `${n} videos`}
                                </option>
                              ))}
                            </select>
                          </li>
                        );
                      })}
                    </ul>
                  </div>
                </Collapse>
              </div>
            </div>

            <div className="flex flex-wrap items-center justify-between gap-4 border-t border-border pt-4">
              <p className="text-sm text-muted-foreground" aria-live="polite">
                {showsSaved && (
                  <>
                    <b className="font-medium text-foreground">{found} creators found</b> by this search. Change the numbers above to search again.
                  </>
                )}
                {!showsSaved && plan.length === 0 && "Choose at least one hashtag to read."}
                {!showsSaved && tooMany && `That is ${total} videos. One search reads at most ${MAX_TOTAL}.`}
                {!showsSaved && tooPricey && `Needs about ${usd(price!.usd)} but only ${usd(left!)} of Apify credit is left.`}
                {!showsSaved && !tooMany && !tooPricey && !price && plan.length > 0 && !error && "Checking the price…"}
                {!showsSaved && !tooMany && !tooPricey && price && plan.length > 0 && (
                  <>
                    {price.cached ? <b className="font-medium text-foreground">Free</b> : <b className="font-medium text-foreground">About {usd(price.usd)}</b>}
                    {price.cached ? ": you already ran this search, so it is read from your saved copy." : left != null ? ` of your ${usd(left)} Apify credit. Nothing is spent until you press search.` : ". Nothing is spent until you press search."}
                    {status === "done" && found > 0 && (
                      <>
                        {" "}
                        <button type="button" onClick={() => router.push(creatorsHref)} className="text-primary underline-offset-4 hover:underline">
                          Or see the {found} creators from your last search
                        </button>
                        .
                      </>
                    )}
                    {status === "done" && found === 0 && " Your last search found no one: try more videos or other hashtags."}
                  </>
                )}
              </p>
              <PillButton onClick={search} loading={starting} disabled={blocked}>
                {showsSaved ? "Show creators" : "Search creators"}
              </PillButton>
            </div>
          </>
        )}
        {(error || status === "error") && (
          <p className="text-sm text-destructive" role="alert">
            {error ?? analysis.creators.error}
          </p>
        )}
      </section>
    </Card>
  );
}
