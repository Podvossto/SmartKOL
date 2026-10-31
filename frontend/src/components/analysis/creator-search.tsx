"use client";

import { ChevronDown, Loader2 } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";

import { PlatformIcon } from "@/components/platform-icon";
import { Card } from "@/components/ui/card";
import { PillButton } from "@/components/ui/pill-button";
import { type CreatorEstimate, type PlanItem, analysisApi } from "@/lib/analysis-api";
import { errorMessage } from "@/lib/errors";
import { usd } from "@/lib/format";
import { cn } from "@/lib/utils";
import { STEPS } from "@/lib/steps";

import { useCurrentAnalysis } from "./context";
import { Origin } from "./origin";
import { Eyebrow } from "./panel";
import { useHashtagList } from "./search-plan";
import { TagEditor } from "./tag-editor";

const CHOICES = [10, 25, 40, 50, 100]; // videos to read per hashtag
const DEFAULT_VIDEOS = 25;
const DEFAULT_TAGS = 3; // a new search starts with the first few hashtags switched on
const MAX_TOTAL = 500; // the server refuses more than this in one search
// New creators per video read, from our real test searches (64 of 75, 71 of 75 and 39 of 45 videos gave a different creator each).
const CREATORS_PER_VIDEO = 0.85;
const CREATORS_TIP = "An estimate from our test searches: about 0.85 different creators per video read. The real number depends on the hashtags.";
type Counts = Record<string, number>;

const fill = (tags: string[], count: number, videos: number): Counts => Object.fromEntries(tags.slice(0, count).map((t) => [t, videos]));
const planOf = (tags: string[], counts: Counts): PlanItem[] => tags.map((t) => ({ hashtag: t, videos: counts[t] ?? 0 })).filter((p) => p.videos > 0);
const byTag = (a: PlanItem, b: PlanItem) => a.hashtag.localeCompare(b.hashtag);
const sameCounts = (a: PlanItem[], b: PlanItem[]) => JSON.stringify([...a].sort(byTag)) === JSON.stringify([...b].sort(byTag)); // the order of the hashtags does not matter
const sum = (plan: PlanItem[]) => plan.reduce((n, p) => n + p.videos, 0);
const aboutCreators = (videos: number) => Math.max(5, Math.round((videos * CREATORS_PER_VIDEO) / 5) * 5);
const plural = (n: number, word: string) => `${n} ${word}${n === 1 ? "" : "s"}`;
type Estimates = { key: string; current?: CreatorEstimate };

function Running({ hashtags, phase }: { hashtags: number; phase: "searching" | "sorting" | null }) {
  const [seconds, setSeconds] = useState(0);
  useEffect(() => {
    const timer = setInterval(() => setSeconds((s) => s + 1), 1000);
    return () => clearInterval(timer);
  }, []);
  return (
    <div className="flex items-center gap-4" role="status">
      <Loader2 className="size-5 shrink-0 animate-spin text-primary" strokeWidth={1.75} />
      <div>
        <p className="font-medium">{phase === "sorting" ? "Telling creators from shops…" : "Searching TikTok…"}</p>
        <p className="text-sm text-muted-foreground">
          {phase === "sorting"
            ? "The AI reads each account's bio and captions, so competitors and shops can be set aside. About half a minute."
            : `Reading the latest videos under ${plural(hashtags, "hashtag")}. Usually under a minute.`}{" "}
          You can leave this page; the search keeps running.
        </p>
      </div>
      <span className="ml-auto font-mono text-sm tabular-nums text-muted-foreground" aria-hidden>
        {seconds}s
      </span>
    </div>
  );
}

/** One card: tick the hashtags to search and pick how many videos to read from each. The price follows the choice; nothing is spent until you press search. */
export function CreatorSearch() {
  const { analysis, adopt } = useCurrentAnalysis();
  const list = useHashtagList();
  const tags = list.tags;
  const router = useRouter();
  const started = useRef(false); // only a search started on this page opens the list; arriving at a finished one does not
  const savedPlan = analysis.creators.plan;
  const [counts, setCounts] = useState<Counts>(() => (savedPlan.length ? Object.fromEntries(savedPlan.map((p) => [p.hashtag, p.videos])) : fill(tags, DEFAULT_TAGS, DEFAULT_VIDEOS)));
  // What a hashtag switched on gets. A saved plan with different counts per hashtag is kept as it is ("Mixed") until this is changed.
  const [videos, setVideos] = useState(() => (new Set(savedPlan.map((p) => p.videos)).size === 1 ? savedPlan[0].videos : DEFAULT_VIDEOS));
  const [prices, setPrices] = useState<Estimates | null>(null);
  const [starting, setStarting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [advanced, setAdvanced] = useState(() => new Set(savedPlan.map((p) => p.videos)).size > 1); // a saved plan with different counts opens the per-hashtag list

  const plan = planOf(tags, counts);
  const total = sum(plan);
  const sizes = new Set(plan.map((p) => p.videos));
  const mixed = sizes.size > 1;
  const each = sizes.size === 1 ? plan[0].videos : videos; // the value the select shows when it is not "Mixed"
  const { status, found } = analysis.creators;
  const key = JSON.stringify([plan, status]);
  const running = status === "running";
  const tooMany = total > MAX_TOTAL;
  const showsSaved = status === "done" && found > 0 && sameCounts(savedPlan, plan); // what is on the page is exactly the saved search

  useEffect(() => {
    let live = true;
    const ask = (p: PlanItem[]) => (p.length > 0 && sum(p) <= MAX_TOTAL ? analysisApi.creatorsEstimate(analysis.id, p) : Promise.resolve(undefined));
    ask(plan)
      .then((current) => live && setPrices({ key, current }))
      .catch((err) => live && setError(errorMessage(err)));
    return () => {
      live = false;
    };
    // the plan is rebuilt every render; `key` is what actually identifies it
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
  const ready = !showsSaved && !tooMany && !tooPricey && !!price && plan.length > 0; // the price is known and the search can go ahead

  // A new hashtag starts switched on; a removed one simply drops out of the plan.
  function changeTags(next: string[]) {
    const added = next.filter((t) => !tags.includes(t));
    if (added.length) setCounts((c) => ({ ...c, ...Object.fromEntries(added.map((t) => [t, each])) }));
    list.setTags(next);
  }

  function setEach(n: number) {
    setVideos(n);
    setCounts((c) => Object.fromEntries(Object.entries(c).map(([t, v]) => [t, v > 0 ? n : 0])));
  }

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
        <div className="flex flex-wrap items-center gap-2">
          <PlatformIcon platform="tiktok" />
          <Eyebrow>Hashtags to search on TikTok</Eyebrow>
          <Origin kind="ai" model={analysis.cost.llm_model} />
          {list.edited && <span className="text-xs text-muted-foreground">Edited by you</span>}
          <span className="ml-auto text-xs text-muted-foreground" role="status" aria-live="polite">
            {list.status === "saving" && "Saving…"}
            {list.status === "saved" && list.isSaved && "Saved"}
          </span>
        </div>
        {running ? (
          <Running hashtags={analysis.creators.hashtags.length || plan.length} phase={analysis.creators.phase} />
        ) : (
          <>
            <TagEditor
              label="1. Pick hashtags"
              hint="Tap one to include or skip it. Add your own below."
              prefix="#"
              tags={tags}
              onChange={changeTags}
              isOn={(t) => (counts[t] ?? 0) > 0}
              onToggle={(t) => setCounts((c) => ({ ...c, [t]: (c[t] ?? 0) > 0 ? 0 : each }))}
              aside={`${plan.length} of ${tags.length} selected`}
            />
            {list.status === "error" && (
              <p className="-mt-2 text-sm text-destructive" role="alert">
                Couldn&apos;t save: {list.error}. Your last change will be tried again when you edit the list.
              </p>
            )}

            <div className="flex flex-col gap-3">
              <div className="flex flex-wrap items-center justify-between gap-x-4 gap-y-2">
                <p className="text-sm font-medium">2. Videos to read from each</p>
                <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
                  {!advanced && (
                    <select aria-label="Videos per hashtag" value={mixed ? "mixed" : each} onChange={(e) => setEach(Number(e.target.value))} className="rounded-full bg-white px-3 py-1 text-sm ring-1 ring-primary/40 focus-visible:outline-2 focus-visible:outline-ring">
                      {mixed && <option value="mixed">Mixed</option>}
                      {!mixed && !CHOICES.includes(each) && <option value={each}>{each} videos</option>}
                      {CHOICES.map((n) => (
                        <option key={n} value={n}>
                          {n} videos
                        </option>
                      ))}
                    </select>
                  )}
                  <button type="button" aria-expanded={advanced} onClick={() => setAdvanced(!advanced)} className="flex items-center gap-1 text-sm text-primary underline-offset-4 hover:underline">
                    {advanced ? "Same for all" : "Set each one"}
                    <ChevronDown className={cn("size-4 transition-transform duration-300", advanced && "rotate-180")} strokeWidth={1.75} />
                  </button>
                </div>
              </div>
              {advanced && plan.length > 0 && (
                <ul aria-label="Videos per hashtag" className="grid gap-x-8 gap-y-1 sm:grid-cols-2">
                  {plan.map((p) => (
                    <li key={p.hashtag} className="flex items-center justify-between gap-3 rounded-xl px-2 py-1 transition-colors hover:bg-muted/50">
                      <label htmlFor={`videos-${p.hashtag}`} className="min-w-0 truncate text-sm">
                        #{p.hashtag}
                      </label>
                      <select
                        id={`videos-${p.hashtag}`}
                        value={p.videos}
                        onChange={(e) => setCounts((c) => ({ ...c, [p.hashtag]: Number(e.target.value) }))}
                        className="rounded-full bg-white px-3 py-1 text-sm ring-1 ring-primary/40 focus-visible:outline-2 focus-visible:outline-ring"
                      >
                        {!CHOICES.includes(p.videos) && <option value={p.videos}>{p.videos} videos</option>}
                        {CHOICES.map((n) => (
                          <option key={n} value={n}>
                            {n} videos
                          </option>
                        ))}
                      </select>
                    </li>
                  ))}
                </ul>
              )}
            </div>

            <div className="flex flex-col gap-4 rounded-2xl bg-muted/40 p-4 sm:flex-row sm:items-center sm:justify-between">
              {ready ? (
                <dl className="grid grid-cols-3 gap-x-6">
                  <div className="flex flex-col-reverse">
                    <dt className="text-xs text-muted-foreground">videos</dt>
                    <dd className="font-medium tabular-nums">{total}</dd>
                  </div>
                  <div className="flex flex-col-reverse" title={price.cached ? `Saved copy of an earlier search. A new one would cost about ${usd(price.list_usd)}.` : left != null ? `Of your ${usd(left)} Apify credit. Nothing is spent until you search.` : "Nothing is spent until you search."}>
                    <dt className="text-xs text-muted-foreground">{price.cached ? "already searched" : "price"}</dt>
                    <dd className="font-medium tabular-nums">{price.cached ? "Free" : `≈ ${usd(price.usd)}`}</dd>
                  </div>
                  <div className="flex flex-col-reverse" title={CREATORS_TIP}>
                    <dt className="text-xs text-muted-foreground">creators (estimated)</dt>
                    <dd className="font-medium tabular-nums">≈ {aboutCreators(total)}</dd>
                  </div>
                </dl>
              ) : (
                <p className="text-sm text-muted-foreground" aria-live="polite">
                  {showsSaved && (
                    <>
                      <b className="font-medium text-foreground">{found} creators found</b> by this search.
                    </>
                  )}
                  {!showsSaved && plan.length === 0 && (tags.length === 0 ? "Add a hashtag to search." : "Pick at least one hashtag.")}
                  {!showsSaved && tooMany && `${total} videos is too many: one search reads at most ${MAX_TOTAL}.`}
                  {!showsSaved && tooPricey && `Needs about ${usd(price!.usd)} but only ${usd(left!)} of Apify credit is left.`}
                  {!showsSaved && !tooMany && !tooPricey && !price && plan.length > 0 && !error && "Checking the price…"}
                </p>
              )}
              <PillButton onClick={search} loading={starting} disabled={blocked} className="w-full shrink-0 sm:w-auto">
                {showsSaved ? "Show creators" : "Search creators"}
              </PillButton>
            </div>
            {status === "done" && found > 0 && !showsSaved && (
              <button type="button" onClick={() => router.push(creatorsHref)} className="-mt-2 w-fit text-sm text-primary underline-offset-4 hover:underline">
                Or see the {found} creators from your last search
              </button>
            )}
            {status === "done" && found === 0 && <p className="-mt-2 text-sm text-muted-foreground">Your last search found no one: try more videos or other hashtags.</p>}
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
