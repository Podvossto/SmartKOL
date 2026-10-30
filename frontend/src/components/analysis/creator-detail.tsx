"use client";

import { BadgeCheck, ExternalLink, Play } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";

import { PlatformIcon } from "@/components/platform-icon";
import { buttonVariants } from "@/components/ui/button";
import { type Creator, analysisApi } from "@/lib/analysis-api";
import { errorMessage } from "@/lib/errors";
import { formatCount, timeAgo } from "@/lib/format";

import { useCurrentAnalysis } from "./context";
import { CreatorAvatar, VideoCover } from "./creator-avatar";
import { CreatorScores } from "./creator-scores";
import { KindBadge } from "./kind-badge";
import { Origin } from "./origin";
import { ChipList, EmptyState, Eyebrow, Rise } from "./panel";

function Stat({ label, value, note }: { label: string; value: string; note?: string }) {
  return (
    <div className="flex min-w-0 flex-col gap-1 rounded-3xl bg-white/70 p-4 ring-1 ring-black/[0.05] sm:p-5">
      <span className="text-xs uppercase tracking-wide text-muted-foreground">{label}</span>
      <span className="font-heading text-xl font-semibold tabular-nums break-words sm:text-2xl">{value}</span>
      {note && <span className="text-xs text-muted-foreground">{note}</span>}
    </div>
  );
}

/** One creator on their own page: who they are, the numbers we have, and the videos the search found. */
export function CreatorDetail() {
  const { analysis } = useCurrentAnalysis();
  const { username: raw } = useParams<{ username: string }>();
  const username = decodeURIComponent(raw);
  const [creator, setCreator] = useState<Creator | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let live = true;
    analysisApi
      .creator(analysis.id, username)
      .then((c) => live && setCreator(c))
      .catch((err) => live && setError(errorMessage(err)));
    return () => {
      live = false;
    };
  }, [analysis.id, username]);

  if (error) {
    return (
      <EmptyState title="Creator not found" text={error}>
        <Link href={`/analysis/${analysis.id}/creators`} className={buttonVariants()}>
          Back to creators
        </Link>
      </EmptyState>
    );
  }
  if (!creator) return <p className="text-muted-foreground">Loading…</p>;

  return (
    <div className="flex flex-col gap-6">
      <Rise>
        <div className="flex flex-wrap items-center gap-5">
          <CreatorAvatar analysisId={analysis.id} creator={creator} className="size-20 shrink-0 text-3xl" />
          <div className="min-w-0 flex-1 basis-40">
            <h2 className="flex items-center gap-2 font-heading text-2xl font-semibold tracking-tight">
              <span className="truncate">{creator.nickname}</span>
              {creator.verified && <BadgeCheck className="size-5 shrink-0 text-primary" aria-label="Verified" />}
            </h2>
            <p className="flex flex-wrap items-center gap-x-2 gap-y-1 break-words text-muted-foreground">
              <span className="flex min-w-0 items-center gap-1.5 break-all">
                <PlatformIcon platform="tiktok" className="size-3.5" /> @{creator.username}
              </span>
              <KindBadge creator={creator} always />
            </p>
            {creator.kind && creator.kind_reason && (
              <p className="mt-1 flex flex-wrap items-center gap-x-2 text-sm text-muted-foreground">
                <span className="min-w-0 break-words">{creator.kind_reason}</span>
                <Origin kind="ai" model={analysis.cost.llm_model} />
              </p>
            )}
          </div>
          <a href={creator.url} target="_blank" rel="noreferrer" className={`${buttonVariants({ variant: "outline" })} w-full sm:w-auto`}>
            Open on TikTok <ExternalLink className="size-4" />
          </a>
        </div>
      </Rise>

      {creator.bio && (
        <Rise index={1}>
          <p className="rounded-3xl bg-white/70 px-6 py-5 text-[15px] leading-relaxed break-words ring-1 ring-black/[0.05]">{creator.bio}</p>
        </Rise>
      )}

      {creator.score && (
        <Rise index={2}>
          <CreatorScores creator={creator} />
        </Rise>
      )}

      <Rise index={2}>
        {creator.metrics ? (
          <section className="flex flex-col gap-3">
            <Eyebrow>Latest {creator.metrics.videos} videos</Eyebrow>
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
              <Stat label="Followers" value={formatCount(creator.followers)} />
              <Stat label="Typical views" value={formatCount(creator.metrics.median_views)} note="Middle of the latest videos" />
              <Stat label="Engagement rate" value={creator.metrics.median_er != null ? `${(creator.metrics.median_er * 100).toFixed(1)}%` : "—"} note="Likes, comments and shares per view" />
              <Stat label="Posts a week" value={creator.metrics.posts_per_week != null ? String(creator.metrics.posts_per_week) : "—"} note={`Last post ${timeAgo(creator.metrics.last_post)}`} />
              <Stat label="Ads" value={`${Math.round(creator.metrics.ad_share * 100)}%`} note="Marked as an ad or sponsored" />
              <Stat label="TikTok Shop" value={`${Math.round(creator.metrics.shop_share * 100)}%`} note="Videos with a shop product" />
              <Stat label="Thai captions" value={`${Math.round(creator.thai_share * 100)}%`} note="In the search results" />
              <Stat label="Total likes" value={formatCount(creator.likes)} note={`${formatCount(creator.total_videos)} videos posted`} />
            </div>
          </section>
        ) : (
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            <Stat label="Followers" value={formatCount(creator.followers)} />
            <Stat label="Typical views" value={formatCount(creator.median_views)} note={`Middle of ${creator.videos_found} video${creator.videos_found === 1 ? "" : "s"} found`} />
            <Stat label="Thai captions" value={`${Math.round(creator.thai_share * 100)}%`} />
            <Stat label="Total likes" value={formatCount(creator.likes)} note={`${formatCount(creator.total_videos)} videos posted`} />
          </div>
        )}
      </Rise>

      <Rise index={3}>
        <section className="flex flex-col gap-3">
          <Eyebrow>Videos found under the hashtags</Eyebrow>
          <ul className="grid grid-cols-1 gap-3 sm:grid-cols-3">
            {creator.samples.map((s, i) => (
              <li key={i} className="flex flex-col overflow-hidden rounded-3xl bg-white/80 ring-1 ring-black/[0.06]">
                <div className="relative">
                  <VideoCover analysisId={analysis.id} creator={creator} index={i} className="aspect-[3/4] w-full" />
                  <span className="absolute bottom-2 left-2 flex items-center gap-1 rounded-full bg-black/60 px-2 py-0.5 text-xs text-white">
                    <Play className="size-3" fill="currentColor" /> {formatCount(s.views)}
                  </span>
                </div>
                <div className="flex flex-1 flex-col justify-between gap-2 p-4">
                  <p className="line-clamp-3 text-sm">{s.text || "No caption."}</p>
                  {s.url && (
                    <a href={s.url} target="_blank" rel="noreferrer" className="flex w-fit items-center gap-1 text-xs text-primary underline-offset-4 hover:underline">
                      Watch on TikTok <ExternalLink className="size-3" />
                    </a>
                  )}
                </div>
              </li>
            ))}
          </ul>
          <p className="text-sm text-muted-foreground">
            Only the videos the hashtag search returned are shown, last seen {timeAgo(creator.last_post)}. A hashtag search usually returns a single video per creator.
          </p>
        </section>
      </Rise>

      <Rise index={4}>
        <section className="flex flex-col gap-2.5">
          <Eyebrow>Found under</Eyebrow>
          <ChipList items={creator.hashtags.map((t) => `#${t}`)} />
          {(creator.ad_videos > 0 || creator.shop_videos > 0) && (
            <p className="text-sm text-muted-foreground">
              Of the videos found, {creator.ad_videos} marked as an ad or sponsored and {creator.shop_videos} with a TikTok Shop product.
            </p>
          )}
        </section>
      </Rise>
    </div>
  );
}
