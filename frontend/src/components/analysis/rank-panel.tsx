"use client";

import { Loader2 } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { Card } from "@/components/ui/card";
import { PillButton } from "@/components/ui/pill-button";
import { type Creator, type EnrichEstimate, analysisApi } from "@/lib/analysis-api";
import { errorMessage } from "@/lib/errors";
import { usd } from "@/lib/format";

import { useCurrentAnalysis } from "./context";
import { Eyebrow } from "./panel";

const HOW_MANY = [5, 10, 20, 30];
const HOW_LONG = [5, 10, 20]; // latest videos read per creator
const MAX_VIDEOS = 500; // the server refuses a bigger read

const pick = "rounded-full bg-white px-3 py-1 text-sm text-foreground ring-1 ring-black/10 focus-visible:outline-2 focus-visible:outline-ring";

/**
 * Turns the list below into a ranking: reads the latest videos of the top creators of the list, then has the AI score
 * them. The price of the video read is shown before anything is spent; a repeat read is free.
 */
export function RankPanel({ creators, onScored }: { creators: Creator[]; onScored: () => void }) {
  const { analysis, adopt } = useCurrentAnalysis();
  const { enrich, scoring } = analysis.creators;
  const [count, setCount] = useState(10);
  const [videos, setVideos] = useState(5);
  const [price, setPrice] = useState<{ key: string; data: EnrichEstimate } | null>(null);
  const [starting, setStarting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const chain = useRef<string[] | null>(null); // the creators to score as soon as their videos have been read

  const names = creators.slice(0, count).map((c) => c.username);
  const key = `${names.join(",")}|${videos}`;
  const tooBig = names.length * videos > MAX_VIDEOS;
  const reading = enrich.status === "running";
  const judging = scoring.status === "running";
  const busy = reading || judging || starting;
  const fresh = price?.key === key ? price.data : null;
  const left = fresh?.account?.remaining_usd ?? null;
  const tooPricey = !!fresh && left != null && fresh.estimate.usd > left;
  const scoredCount = creators.filter((c) => c.score).length;

  useEffect(() => {
    if (names.length === 0 || tooBig) return;
    let live = true;
    analysisApi
      .enrichEstimate(analysis.id, names, videos)
      .then((data) => live && (setPrice({ key, data }), setError(null)))
      .catch((err) => live && setError(errorMessage(err)));
    return () => {
      live = false;
    };
    // `key` identifies the names and the video count
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [analysis.id, key, tooBig]);

  // reading finished -> hand the same creators to the scoring
  const scoringStatus = scoring.status;
  useEffect(() => {
    const next = chain.current;
    if (!next) return;
    if (enrich.status === "error") {
      chain.current = null;
    } else if (enrich.status === "done" && scoringStatus !== "running") {
      chain.current = null;
      analysisApi.score(analysis.id, next).then(adopt).catch((err) => setError(errorMessage(err)));
    }
  }, [enrich.status, scoringStatus, analysis.id, adopt]);

  // scoring finished -> tell the page, which shows the ranking
  const wasJudging = useRef(false);
  useEffect(() => {
    if (wasJudging.current && scoringStatus === "done") onScored();
    wasJudging.current = scoringStatus === "running";
  }, [scoringStatus, onScored]);

  async function run() {
    setStarting(true);
    setError(null);
    try {
      adopt(await analysisApi.enrich(analysis.id, names, videos));
      chain.current = names; // only once the server says "running", or the old "done" would trigger the scoring too early
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setStarting(false);
    }
  }

  const failure = error ?? (enrich.status === "error" ? enrich.error : scoring.status === "error" ? scoring.error : null);

  return (
    <Card>
      <section className="flex flex-col gap-4 px-(--card-spacing)">
        <Eyebrow>Rank creators</Eyebrow>
        {busy ? (
          <div className="flex items-center gap-4" role="status">
            <Loader2 className="size-5 animate-spin text-primary" strokeWidth={1.75} />
            <p>
              <span className="font-medium">{judging ? "Scoring…" : `Reading the latest videos of ${names.length} creators…`}</span>
              <span className="block text-sm text-muted-foreground">
                {judging ? "The AI judges how well each creator fits the brand. Usually under a minute." : "Takes about a minute. You can leave this page; it keeps running."}
              </span>
            </p>
          </div>
        ) : (
          <div className="flex flex-wrap items-center justify-between gap-4">
            <div className="flex flex-col gap-2">
              <p className="flex flex-wrap items-center gap-x-2 gap-y-2 text-sm">
                Read the latest
                <select aria-label="Videos per creator" value={videos} onChange={(e) => setVideos(Number(e.target.value))} className={pick}>
                  {HOW_LONG.map((n) => (
                    <option key={n} value={n}>
                      {n} videos
                    </option>
                  ))}
                </select>
                of the top
                <select aria-label="Number of creators" value={count} onChange={(e) => setCount(Number(e.target.value))} className={pick}>
                  {HOW_MANY.map((n) => (
                    <option key={n} value={n}>
                      {n} creators
                    </option>
                  ))}
                </select>
                in the list below, then score them.
              </p>
              <p className="text-sm text-muted-foreground" aria-live="polite">
                {tooBig && `That is ${names.length * videos} videos. One read takes at most ${MAX_VIDEOS}.`}
                {!tooBig && names.length === 0 && "No creators in the list to read."}
                {!tooBig && names.length > 0 && !fresh && !error && "Checking the price…"}
                {!tooBig && fresh && tooPricey && `Reading needs about ${usd(fresh.estimate.usd)} but only ${usd(left!)} of Apify credit is left.`}
                {!tooBig && fresh && !tooPricey && (
                  <>
                    <b className="font-medium text-foreground">{fresh.estimate.cached ? "Free" : `About ${usd(fresh.estimate.usd)}`}</b>
                    {fresh.estimate.cached ? ": you read these before, so it comes from your saved copy." : left != null ? ` of your ${usd(left)} Apify credit to read ${fresh.estimate.videos} videos.` : ` to read ${fresh.estimate.videos} videos.`} The AI scoring adds a fraction of a cent. Nothing is spent until you press the button.
                  </>
                )}
                {scoredCount > 0 && ` ${scoredCount} creators in this list are scored.`}
              </p>
            </div>
            <PillButton onClick={run} loading={starting} disabled={tooBig || tooPricey || !fresh || names.length === 0}>
              {scoredCount > 0 ? "Read and score again" : "Read and score"}
            </PillButton>
          </div>
        )}
        {failure && (
          <p className="text-sm text-destructive" role="alert">
            {failure}
          </p>
        )}
        {!busy && scoring.status === "done" && scoring.failed ? (
          <p className="text-sm text-amber-800" role="status">
            The AI did not answer for {scoring.failed} creators; they stay unscored. Press the button to try them again.
          </p>
        ) : null}
        {!busy && enrich.status === "done" && enrich.missing && enrich.missing.length > 0 && (
          <p className="text-sm text-amber-800" role="status">
            No recent videos came back for {enrich.missing.map((u) => `@${u}`).join(", ")} (private or empty accounts); they cannot be scored.
          </p>
        )}
      </section>
    </Card>
  );
}
