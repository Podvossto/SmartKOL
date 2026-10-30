import type { Creator } from "@/lib/analysis-api";
import { cn } from "@/lib/utils";

const LABELS = { shop: "Shop", media: "Page", other: "Unclear" } as const;

/** Says what the AI took the account to be, when it is not a plain creator. A shop that sells what the brand sells is called a competitor. */
export function KindBadge({ creator, always }: { creator: Creator; always?: boolean }) {
  const { kind, competitor } = creator;
  if (!kind || (kind === "creator" && !always)) return null;
  const label = competitor ? "Competitor" : kind === "creator" ? "Creator" : LABELS[kind];
  return (
    <span
      title="Sorted by the AI from the account's bio and captions"
      className={cn("shrink-0 rounded-full px-2 py-0.5 text-[11px] font-medium", competitor ? "bg-amber-100 text-amber-800" : kind === "creator" ? "bg-primary/10 text-primary" : "bg-muted text-muted-foreground")}
    >
      {label}
    </span>
  );
}
