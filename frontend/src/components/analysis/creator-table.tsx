"use client";

import { ArrowDown, ArrowUp, ExternalLink } from "lucide-react";
import { useRouter } from "next/navigation";

import type { Creator } from "@/lib/analysis-api";
import { formatCount, timeAgo } from "@/lib/format";
import { cn } from "@/lib/utils";

import { CreatorAvatar } from "./creator-avatar";
import { FlagBadge } from "./flag-badge";
import { KindBadge } from "./kind-badge";
import { type Sort, type SortKey, viewsOf } from "./creator-sort";
import { ScoreCell } from "./score-cell";

export const creatorHref = (analysisId: string, c: Creator) => `/analysis/${analysisId}/creators/${encodeURIComponent(c.username)}`;

type Column = { key: SortKey; label: string; className?: string };
const BASE: Column[] = [
  { key: "followers", label: "Followers", className: "hidden sm:table-cell" },
  { key: "median_views", label: "Typical views", className: "hidden sm:table-cell" },
  { key: "thai_share", label: "Thai captions", className: "hidden sm:table-cell" },
  { key: "last_post", label: "Last post", className: "hidden md:table-cell" },
];
// Shown once creators have been read and scored; the four axes only from a wide screen, the total always.
const SCORED: Column[] = [{ key: "total", label: "Score" }];
const AXES: Column[] = [
  { key: "relevance", label: "Brand fit", className: "hidden lg:table-cell" },
  { key: "engagement", label: "Engagement", className: "hidden xl:table-cell" },
  { key: "audience", label: "Audience*", className: "hidden xl:table-cell" },
  { key: "activity", label: "Activity", className: "hidden xl:table-cell" },
];
const RATE: Column = { key: "er", label: "Eng. rate", className: "hidden md:table-cell" };

function Head({ column, sort, onSort }: { column: Column; sort: Sort; onSort: (key: SortKey) => void }) {
  const active = sort.key === column.key;
  return (
    <th scope="col" aria-sort={active ? (sort.dir === "asc" ? "ascending" : "descending") : "none"} className={cn("px-3 py-3 text-left font-medium", column.className)}>
      <button type="button" onClick={() => onSort(column.key)} className={cn("inline-flex items-center gap-1 transition-colors hover:text-foreground", active && "text-foreground")}>
        {column.label}
        {active && (sort.dir === "asc" ? <ArrowUp className="size-3" /> : <ArrowDown className="size-3" />)}
      </button>
    </th>
  );
}

/** One row per creator, columns to compare and sort by. A row opens that creator's page. */
export function CreatorTable({ analysisId, creators, sort, onSort }: { analysisId: string; creators: Creator[]; sort: Sort; onSort: (key: SortKey) => void }) {
  const router = useRouter();
  const scored = creators.some((c) => c.score);
  const read = creators.some((c) => c.metrics);
  const columns = [...(scored ? SCORED : []), ...BASE.filter((c) => !(scored && c.key === "thai_share")), ...(read ? [RATE] : []), ...(scored ? AXES : [])];
  return (
    <div className="relative overflow-hidden rounded-3xl bg-white/80 ring-1 ring-black/[0.06]">
      <table className="w-full text-sm">
        <thead className="border-b border-border text-xs uppercase tracking-wide text-muted-foreground">
          <tr>
            <Head column={{ key: "name", label: "Creator" }} sort={sort} onSort={onSort} />
            {columns.map((c) => (
              <Head key={c.key} column={c} sort={sort} onSort={onSort} />
            ))}
            {!scored && (
              <th scope="col" className="hidden px-3 py-3 text-left font-medium lg:table-cell">
                Bio
              </th>
            )}
            <th scope="col" className="w-10 px-3 py-3">
              <span className="sr-only">Open on TikTok</span>
            </th>
          </tr>
        </thead>
        <tbody className="divide-y divide-border">
          {creators.map((c) => (
            <tr key={c.username} onClick={() => router.push(creatorHref(analysisId, c))} className="cursor-pointer transition-colors hover:bg-primary/[0.04]">
              <td className="w-full max-w-0 px-3 py-3">
                <a
                  href={creatorHref(analysisId, c)}
                  onClick={(e) => {
                    e.preventDefault();
                    e.stopPropagation();
                    router.push(creatorHref(analysisId, c));
                  }}
                  className="flex min-w-0 items-center gap-3"
                >
                  <CreatorAvatar analysisId={analysisId} creator={c} className="size-9 text-sm" />
                  <span className="flex min-w-0 flex-col">
                    <span className="flex items-center gap-1.5">
                      <span className="truncate font-medium">{c.nickname}</span>
                      <KindBadge creator={c} />
                      <FlagBadge creator={c} />
                    </span>
                    <span className="truncate text-xs text-muted-foreground">@{c.username}</span>
                    <span className="truncate text-xs text-muted-foreground sm:hidden">
                      {formatCount(c.followers)} followers · {formatCount(viewsOf(c))} views
                    </span>
                  </span>
                </a>
              </td>
              {scored && (
                <td className="px-3 py-3">
                  <span className="flex items-center gap-2">
                    {c.rank != null && <span className="w-6 text-xs text-muted-foreground tabular-nums">#{c.rank}</span>}
                    <ScoreCell value={c.total} strong />
                  </span>
                </td>
              )}
              <td className="hidden px-3 py-3 tabular-nums sm:table-cell">{formatCount(c.followers)}</td>
              <td className={`hidden px-3 py-3 tabular-nums sm:table-cell ${read && !c.metrics ? "text-muted-foreground/60" : ""}`} title={read && !c.metrics ? "From one video found in the search: not read yet" : undefined}>{formatCount(viewsOf(c))}</td>
              {!scored && <td className="hidden px-3 py-3 tabular-nums sm:table-cell">{Math.round(c.thai_share * 100)}%</td>}
              <td className="hidden px-3 py-3 text-muted-foreground md:table-cell">{timeAgo(c.metrics?.last_post ?? c.last_post)}</td>
              {read && <td className="hidden px-3 py-3 tabular-nums md:table-cell">{c.metrics?.median_er != null ? `${(c.metrics.median_er * 100).toFixed(1)}%` : "—"}</td>}
              {scored && (
                <>
                  <td className="hidden px-3 py-3 lg:table-cell">
                    <ScoreCell value={c.score?.relevance} />
                  </td>
                  <td className="hidden px-3 py-3 xl:table-cell">
                    <ScoreCell value={c.score?.engagement} />
                  </td>
                  <td className="hidden px-3 py-3 xl:table-cell">
                    <ScoreCell value={c.score?.audience} estimated />
                  </td>
                  <td className="hidden px-3 py-3 xl:table-cell">
                    <ScoreCell value={c.score?.activity} />
                  </td>
                </>
              )}
              {!scored && (
                <td className="hidden max-w-xs px-3 py-3 text-muted-foreground lg:table-cell">
                  <span className="line-clamp-2 text-xs">{c.bio}</span>
                </td>
              )}
              <td className="px-3 py-3">
                <a href={c.url} target="_blank" rel="noreferrer" onClick={(e) => e.stopPropagation()} aria-label={`Open @${c.username} on TikTok`} className="text-muted-foreground transition-colors hover:text-primary">
                  <ExternalLink className="size-4" />
                </a>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
