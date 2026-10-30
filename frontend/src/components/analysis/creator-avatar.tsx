"use client";

import { useState } from "react";

import { type Creator, creatorPictureUrl } from "@/lib/analysis-api";
import { cn } from "@/lib/utils";

/** The creator's picture as kept by our server; their initial when there is none or it can't be loaded. */
export function CreatorAvatar({ analysisId, creator, className }: { analysisId: string; creator: Creator; className?: string }) {
  const [failed, setFailed] = useState(false);
  if (creator.has_avatar && !failed) {
    return (
      // eslint-disable-next-line @next/next/no-img-element
      <img src={creatorPictureUrl(analysisId, creator.username, "avatar")} alt="" loading="lazy" onError={() => setFailed(true)} className={cn("shrink-0 rounded-full bg-muted object-cover", className)} />
    );
  }
  return <span aria-hidden className={cn("grid shrink-0 place-items-center rounded-full bg-primary/10 font-medium text-primary", className)}>{(creator.nickname || creator.username).trim().charAt(0).toUpperCase()}</span>;
}

/** The cover of one of the creator's videos, or a neutral tile when it can't be shown. */
export function VideoCover({ analysisId, creator, index, className }: { analysisId: string; creator: Creator; index: number; className?: string }) {
  const [failed, setFailed] = useState(false);
  if (creator.samples[index]?.has_cover && !failed) {
    return (
      // eslint-disable-next-line @next/next/no-img-element
      <img src={creatorPictureUrl(analysisId, creator.username, index)} alt="" loading="lazy" onError={() => setFailed(true)} className={cn("bg-muted object-cover", className)} />
    );
  }
  return <span aria-hidden className={cn("block bg-muted/70", className)} />;
}
