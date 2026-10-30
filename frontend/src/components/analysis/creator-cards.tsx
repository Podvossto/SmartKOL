"use client";

import { BadgeCheck, ExternalLink } from "lucide-react";
import Link from "next/link";

import { PlatformIcon } from "@/components/platform-icon";
import type { Creator } from "@/lib/analysis-api";
import { formatCount } from "@/lib/format";

import { CreatorAvatar, VideoCover } from "./creator-avatar";
import { viewsOf } from "./creator-sort";
import { KindBadge } from "./kind-badge";
import { creatorHref } from "./creator-table";

function CreatorCard({ analysisId, creator: c }: { analysisId: string; creator: Creator }) {
  const covers = c.samples.flatMap((s, i) => (s.has_cover ? [i] : []));
  return (
    <li className="group relative flex flex-col gap-3 rounded-3xl bg-white/90 p-4 ring-1 ring-black/[0.06] transition-all duration-300 hover:-translate-y-1 hover:shadow-[0_20px_40px_-18px_rgba(20,30,80,0.3)]">
      <div className="flex items-center gap-3">
        <CreatorAvatar analysisId={analysisId} creator={c} className="size-11 text-base" />
        <div className="min-w-0 flex-1">
          <Link href={creatorHref(analysisId, c)} className="flex items-center gap-1.5 font-medium after:absolute after:inset-0 after:rounded-3xl">
            <PlatformIcon platform="tiktok" className="size-3.5" />
            <span className="truncate">@{c.username}</span>
            {c.verified && <BadgeCheck className="size-4 shrink-0 text-primary" aria-label="Verified" />}
          </Link>
          <p className="flex items-center gap-1.5 text-sm text-muted-foreground">
            <span className="truncate">{c.nickname}</span>
            <KindBadge creator={c} />
          </p>
        </div>
        {c.total != null && (
          <span className="flex flex-col items-end leading-none" title={`Rank #${c.rank} by total score`}>
            <span className="font-heading text-xl font-semibold tabular-nums">{c.total}</span>
            <span className="text-[10px] text-muted-foreground">#{c.rank}</span>
          </span>
        )}
        <a href={c.url} target="_blank" rel="noreferrer" aria-label={`Open @${c.username} on TikTok`} className="relative z-10 rounded-full p-1.5 text-muted-foreground transition-colors hover:bg-muted hover:text-primary">
          <ExternalLink className="size-4" />
        </a>
      </div>
      <p className="line-clamp-2 min-h-10 text-sm text-muted-foreground">{c.bio || "No bio."}</p>
      {covers.length > 0 && (
        // one video fills the strip; several share it in three columns
        <div className={covers.length === 1 ? "overflow-hidden rounded-2xl" : "grid grid-cols-3 gap-1.5 overflow-hidden rounded-2xl"}>
          {covers.map((i) => (
            <VideoCover key={i} analysisId={analysisId} creator={c} index={i} className={covers.length === 1 ? "aspect-[16/10] w-full" : "aspect-[3/4] w-full"} />
          ))}
        </div>
      )}
      <p className="flex flex-wrap gap-x-4 gap-y-0.5 text-xs text-muted-foreground">
        <span>
          <b className="font-medium text-foreground">{formatCount(c.followers)}</b> followers
        </span>
        <span>
          <b className="font-medium text-foreground">{formatCount(viewsOf(c))}</b> typical views
        </span>
        <span>Thai {Math.round(c.thai_share * 100)}%</span>
      </p>
    </li>
  );
}

/** The same creators as pictures: who they are and what their videos look like, at a glance. */
export function CreatorCards({ analysisId, creators }: { analysisId: string; creators: Creator[] }) {
  return (
    <ul className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
      {creators.map((c) => (
        <CreatorCard key={c.username} analysisId={analysisId} creator={c} />
      ))}
    </ul>
  );
}
