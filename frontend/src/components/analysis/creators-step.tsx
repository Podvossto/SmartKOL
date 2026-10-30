"use client";

import { LayoutGrid, Rows3 } from "lucide-react";
import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";

import { buttonVariants } from "@/components/ui/button";
import { type CreatorFilters, type CreatorList, analysisApi } from "@/lib/analysis-api";
import { errorMessage } from "@/lib/errors";
import { cn } from "@/lib/utils";

import { useCurrentAnalysis } from "./context";
import { CreatorCards } from "./creator-cards";
import { CreatorFilterPanel, DEFAULT_FILTERS } from "./creator-filters";
import { SORT_LABELS, type Sort, type SortKey, sortCreators } from "./creator-sort";
import { CreatorTable } from "./creator-table";
import { EmptyState, Rise } from "./panel";
import { RankPanel } from "./rank-panel";

const PAGE = 20;
type View = "table" | "cards";
const VIEWS: { id: View; label: string; icon: typeof Rows3 }[] = [
  { id: "table", label: "Table", icon: Rows3 },
  { id: "cards", label: "Cards", icon: LayoutGrid },
];

/** Everyone the search found, as a table to compare or as cards to browse. Filters and sorting never cost anything. */
export function CreatorsStep() {
  const { analysis } = useCurrentAnalysis();
  const [filters, setFilters] = useState(DEFAULT_FILTERS);
  const [listing, setListing] = useState<CreatorList | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [view, setView] = useState<View>("table");
  const [picked, setSort] = useState<Sort | null>(null); // null: the default order, which is the ranking once there is one
  const [shown, setShown] = useState(PAGE);
  const found = analysis.creators.found;
  const searchedAt = analysis.creators.searched_at;

  useEffect(() => {
    if (found === 0) return;
    let live = true;
    analysisApi
      .creators(analysis.id, filters)
      .then((data) => live && (setListing(data), setError(null)))
      .catch((err) => live && setError(errorMessage(err)));
    return () => {
      live = false;
    };
  }, [analysis.id, filters, found, searchedAt]);

  // The ranking is the point of scoring: best-first as soon as scores exist, until the user sorts otherwise.
  const scored = listing?.kept.some((c) => c.score) ?? false;
  const sort: Sort = picked ?? (scored ? { key: "total", dir: "desc" } : { key: "followers", dir: "desc" });
  const sorted = useMemo(() => (listing ? sortCreators(listing.kept, sort) : []), [listing, sort.key, sort.dir]); // eslint-disable-line react-hooks/exhaustive-deps
  const showRanking = useCallback(() => {
    setSort(null);
    analysisApi.creators(analysis.id, filters).then(setListing).catch((err) => setError(errorMessage(err)));
  }, [analysis.id, filters]);

  if (found === 0) {
    return (
      <EmptyState title="No creators yet" text="Run a search first. The creators it finds are listed here.">
        <Link href={`/analysis/${analysis.id}/search`} className={buttonVariants()}>
          Go to search
        </Link>
      </EmptyState>
    );
  }

  const change = (c: Partial<CreatorFilters>) => {
    setFilters((f) => ({ ...f, ...c }));
    setShown(PAGE);
  };
  const sortBy = (key: SortKey) => setSort(sort.key === key ? { key, dir: sort.dir === "asc" ? "desc" : "asc" } : { key, dir: key === "name" ? "asc" : "desc" });

  return (
    <div className="flex flex-col gap-6">
      <Rise>
        <h2 className="font-heading text-2xl font-semibold tracking-tight">Creators</h2>
        <p className="text-muted-foreground">
          {found} creators from {analysis.creators.videos} videos · {analysis.creators.cached ? "from your saved search, $0" : `search cost $${analysis.creators.usd.toFixed(2)}`}
        </p>
      </Rise>
      {analysis.creators.classify_error && (
        <p className="rounded-2xl bg-amber-50 px-4 py-3 text-sm text-amber-800 ring-1 ring-amber-200" role="status">
          {analysis.creators.classify_error} Shops are only hidden where the AI labelled them.
        </p>
      )}
      <Rise index={1}>
        <RankPanel creators={sorted} onScored={showRanking} />
      </Rise>
      <Rise index={1}>
        <CreatorFilterPanel filters={filters} onChange={change} dropped={listing?.dropped} />
      </Rise>
      <Rise index={2}>
        <div className="flex flex-col gap-4" aria-live="polite">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <p className="text-sm font-medium">{listing ? `${listing.kept.length} of ${listing.total} creators match` : "Loading…"}</p>
            <div className="flex flex-wrap items-center gap-3">
              <label className="flex items-center gap-2 text-sm text-muted-foreground">
                Sort by
                <select
                  value={sort.key}
                  onChange={(e) => setSort({ key: e.target.value as SortKey, dir: e.target.value === "name" ? "asc" : "desc" })}
                  className="rounded-full bg-white px-3 py-1.5 text-sm text-foreground ring-1 ring-black/10 focus-visible:outline-2 focus-visible:outline-ring"
                >
                  {(Object.keys(SORT_LABELS) as SortKey[]).map((k) => (
                    <option key={k} value={k}>
                      {SORT_LABELS[k]}
                    </option>
                  ))}
                </select>
              </label>
              <div role="group" aria-label="View" className="flex gap-1 rounded-full bg-muted p-1">
                {VIEWS.map(({ id, label, icon: Icon }) => (
                  <button
                    key={id}
                    type="button"
                    aria-pressed={view === id}
                    onClick={() => setView(id)}
                    className={cn("flex items-center gap-1.5 rounded-full px-3 py-1.5 text-sm transition-all duration-300", view === id ? "bg-white font-medium shadow-sm" : "text-muted-foreground hover:text-foreground")}
                  >
                    <Icon className="size-4" strokeWidth={1.75} /> {label}
                  </button>
                ))}
              </div>
            </div>
          </div>
          {error && (
            <p className="text-sm text-destructive" role="alert">
              {error}
            </p>
          )}
          {listing && sorted.length === 0 && <p className="rounded-3xl bg-white/60 px-6 py-12 text-center text-sm text-muted-foreground ring-1 ring-black/[0.05]">No one matches these filters. Loosen one above, or search again with more videos.</p>}
          {sorted.length > 0 && (view === "table" ? <CreatorTable analysisId={analysis.id} creators={sorted.slice(0, shown)} sort={sort} onSort={sortBy} /> : <CreatorCards analysisId={analysis.id} creators={sorted.slice(0, shown)} />)}
          {scored && sorted.length > 0 && view === "table" && (
            <p className="text-xs text-muted-foreground">
              Scores are 0-100. * Audience fit is the AI&apos;s estimate from the creator&apos;s content: TikTok does not show who watches. Unscored creators have not been read yet.
            </p>
          )}
          {sorted.length > shown && (
            <button type="button" onClick={() => setShown((n) => n + PAGE)} className="w-fit text-sm text-primary underline-offset-4 hover:underline">
              Show {Math.min(PAGE, sorted.length - shown)} more
            </button>
          )}
        </div>
      </Rise>
    </div>
  );
}
