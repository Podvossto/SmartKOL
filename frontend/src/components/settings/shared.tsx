import { Badge } from "@/components/ui/badge";

export { errorMessage } from "@/lib/errors";

export const usd = (n: number, digits = 2) => `$${n.toFixed(digits)}`;

export function SourceBadge({ source }: { source: "ui" | "env" | "none" }) {
  if (source === "ui") return <Badge>Saved in app</Badge>;
  if (source === "env") return <Badge variant="secondary">Set by server file</Badge>;
  return <Badge variant="outline">Not set</Badge>;
}

/** Service name with its mark, used as the title of each card. */
export function ServiceTitle({ logo, children }: { logo?: string; children: React.ReactNode }) {
  return (
    <span className="flex items-center gap-2.5">
      {logo && (
        // eslint-disable-next-line @next/next/no-img-element
        <img src={logo} alt="" className="size-7 rounded-lg bg-white object-contain ring-1 ring-black/[0.06]" />
      )}
      {children}
    </span>
  );
}

/** A small "label: message" line under a field, red when it is a problem. */
export function FieldNote({ id, error, children }: { id?: string; error?: boolean; children: React.ReactNode }) {
  return (
    <p id={id} role={error ? "alert" : undefined} className={error ? "text-sm text-destructive" : "text-xs text-muted-foreground"}>
      {children}
    </p>
  );
}
