import { cn } from "@/lib/utils";

/** A 0-100 score as a number over a thin bar, so a column of them can be compared by eye. */
export function ScoreCell({ value, strong, estimated }: { value: number | undefined | null; strong?: boolean; estimated?: boolean }) {
  if (value == null) return <span className="text-muted-foreground">—</span>;
  return (
    <span className="flex min-w-14 flex-col gap-1" title={estimated ? "Estimated by the AI from the creator's content" : undefined}>
      <span className={cn("tabular-nums", strong ? "text-base font-semibold" : "text-sm")}>
        {value}
        {estimated && <span className="text-muted-foreground">*</span>}
      </span>
      <span className="h-1 w-full overflow-hidden rounded-full bg-muted">
        <span className={cn("block h-full rounded-full", estimated ? "bg-primary/40" : "bg-primary")} style={{ width: `${value}%` }} />
      </span>
    </span>
  );
}

/** The model's guess at who watches a creator, in a few words: "18-24 · mostly women". Empty when there is none. */
export function viewersLine(viewers: { age: string; gender: string; interests: string[] } | null | undefined, withInterests = false): string {
  if (!viewers) return "";
  return [viewers.age, viewers.gender, withInterests && viewers.interests.join(", ")].filter(Boolean).join(" · ");
}
