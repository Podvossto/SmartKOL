import type { Creator } from "@/lib/analysis-api";

export type SortKey = "followers" | "median_views" | "thai_share" | "last_post" | "name";
export type Sort = { key: SortKey; dir: "asc" | "desc" };

export const SORT_LABELS: Record<SortKey, string> = {
  followers: "Followers",
  median_views: "Typical views",
  thai_share: "Thai captions",
  last_post: "Seen most recently",
  name: "Name",
};

const value = (c: Creator, key: SortKey): number | string => {
  if (key === "name") return c.nickname.toLowerCase();
  if (key === "last_post") return c.last_post ? Date.parse(c.last_post) : 0;
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
