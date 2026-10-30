import { TriangleAlert } from "lucide-react";

import type { Creator } from "@/lib/analysis-api";

/** A warning mark beside a scored creator whose score came with a caution (brand safety capped it, many ads, followers that look inflated). The words are in the tooltip, so the list stays quiet until something is wrong. */
export function FlagBadge({ creator }: { creator: Creator }) {
  const flags = creator.score?.flags ?? [];
  if (flags.length === 0) return null;
  const text = flags.join(" ");
  return (
    <span title={text} role="img" aria-label={`Warning: ${text}`} className="inline-flex shrink-0 items-center gap-1 rounded-full bg-amber-100 px-2 py-0.5 text-[11px] font-medium text-amber-800">
      <TriangleAlert className="size-3" strokeWidth={2} /> Check
    </span>
  );
}
