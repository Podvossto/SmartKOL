import { ArrowLeft } from "lucide-react";
import Link from "next/link";

import { cn } from "@/lib/utils";

/** One step back, always in the same style: the arrow leans out on hover. */
export function BackLink({ href, label, className }: { href: string; label: string; className?: string }) {
  return (
    <Link href={href} className={cn("group flex w-fit items-center gap-1.5 rounded-full py-1 pr-3 text-sm text-muted-foreground transition-colors hover:text-foreground", className)}>
      <ArrowLeft className="size-4 transition-transform duration-500 ease-[cubic-bezier(0.32,0.72,0,1)] group-hover:-translate-x-1" strokeWidth={1.75} /> {label}
    </Link>
  );
}
