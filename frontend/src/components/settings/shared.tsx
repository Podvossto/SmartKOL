import { Badge } from "@/components/ui/badge";

export function errorMessage(err: unknown): string {
  return err instanceof Error ? err.message : "Something went wrong";
}

export const usd = (n: number, digits = 2) => `$${n.toFixed(digits)}`;

export function SourceBadge({ source }: { source: "ui" | "env" | "none" }) {
  if (source === "ui") return <Badge>Saved in app</Badge>;
  if (source === "env") return <Badge variant="secondary">From credential/.env</Badge>;
  return <Badge variant="outline">Not set</Badge>;
}
