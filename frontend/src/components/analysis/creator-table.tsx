"use client";

import { ArrowDown, ArrowUp, ExternalLink } from "lucide-react";
import { useRouter } from "next/navigation";

import type { Creator } from "@/lib/analysis-api";
import { formatCount, timeAgo } from "@/lib/format";
import { cn } from "@/lib/utils";

import { CreatorAvatar } from "./creator-avatar";
import { KindBadge } from "./kind-badge";
import type { Sort, SortKey } from "./creator-sort";

export const creatorHref = (analysisId: string, c: Creator) => `/analysis/${analysisId}/creators/${encodeURIComponent(c.username)}`;

type Column = { key: SortKey; label: string; className?: string };
const COLUMNS: Column[] = [
  { key: "followers", label: "Followers" },
  { key: "median_views", label: "Typical views" },
  { key: "thai_share", label: "Thai captions", className: "hidden sm:table-cell" },
  { key: "last_post", label: "Seen", className: "hidden md:table-cell" },
];

function Head({ column, sort, onSort }: { column: Column; sort: Sort; onSort: (key: SortKey) => void }) {
  const active = sort.key === column.key;
  return (
    <th scope="col" aria-sort={active ? (sort.dir === "asc" ? "ascending" : "descending") : "none"} className={cn("px-4 py-3 text-left font-medium", column.className)}>
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
  return (
    <div className="relative overflow-x-auto rounded-3xl bg-white/80 ring-1 ring-black/[0.06]">
      <table className="w-full text-sm">
        <thead className="border-b border-border text-xs uppercase tracking-wide text-muted-foreground">
          <tr>
            <Head column={{ key: "name", label: "Creator" }} sort={sort} onSort={onSort} />
            {COLUMNS.map((c) => (
              <Head key={c.key} column={c} sort={sort} onSort={onSort} />
            ))}
            <th scope="col" className="hidden px-4 py-3 text-left font-medium lg:table-cell">
              Bio
            </th>
            <th scope="col" className="w-10 px-4 py-3">
              <span className="sr-only">Open on TikTok</span>
            </th>
          </tr>
        </thead>
        <tbody className="divide-y divide-border">
          {creators.map((c) => (
            <tr key={c.username} onClick={() => router.push(creatorHref(analysisId, c))} className="cursor-pointer transition-colors hover:bg-primary/[0.04]">
              <td className="px-4 py-3">
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
                    </span>
                    <span className="truncate text-xs text-muted-foreground">@{c.username}</span>
                  </span>
                </a>
              </td>
              <td className="px-4 py-3 tabular-nums">{formatCount(c.followers)}</td>
              <td className="px-4 py-3 tabular-nums">{formatCount(c.median_views)}</td>
              <td className="hidden px-4 py-3 tabular-nums sm:table-cell">{Math.round(c.thai_share * 100)}%</td>
              <td className="hidden px-4 py-3 text-muted-foreground md:table-cell">{timeAgo(c.last_post)}</td>
              <td className="hidden max-w-xs px-4 py-3 text-muted-foreground lg:table-cell">
                <span className="line-clamp-2 text-xs">{c.bio}</span>
              </td>
              <td className="px-4 py-3">
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
