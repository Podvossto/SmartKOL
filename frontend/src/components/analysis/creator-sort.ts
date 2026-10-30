import type { Creator } from "@/lib/analysis-api";

export type SortKey = "total" | "relevance" | "engagement" | "audience" | "activity" | "er" | "followers" | "median_views" | "thai_share" | "last_post" | "name";
export type Sort = { key: SortKey; dir: "asc" | "desc" };

export const SORT_LABELS: Record<SortKey, string> = {
  total: "Total score",
  relevance: "Relevance",
  engagement: "Engagement score",
  audience: "Audience fit",
  activity: "Activity",
  er: "Engagement rate",
  followers: "Followers",
  median_views: "Typical views",
  thai_share: "Thai captions",
  last_post: "Seen most recently",
  name: "Name",
};

/** Typical views: from the creator's own latest videos once they have been read, otherwise from the search. */
export const viewsOf = (c: Creator) => c.metrics?.median_views ?? c.median_views;

const value = (c: Creator, key: SortKey): number | string => {
  if (key === "name") return c.nickname.toLowerCase();
  if (key === "last_post") return c.last_post ? Date.parse(c.last_post) : 0;
  if (key === "median_views") return viewsOf(c);
  if (key === "total") return c.total ?? -1; // unscored creators sink to the bottom
  if (key === "er") return c.metrics?.median_er ?? -1;
  if (key === "relevance" || key === "engagement" || key === "audience" || key === "activity") return c.score?.[key] ?? -1;
  return c[key] ?? 0;
};

export function sortCreators(list: Creator[], { key, dir }: Sort): Creator[] {
  const sign = dir === "asc" ? 1 : -1;
  return [...list].sort((a, b) => {
    const x = value(a, key);
    const y = value(b, key);
    return (x < y ? -1 : x > y ? 1 : 0) * sign;
  });
}
