"use client";

import { Settings } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";

import { HowItWorksButton } from "@/components/how-it-works";
import { UsageMenu } from "@/components/usage-menu";
import { cn } from "@/lib/utils";

const item = "rounded-full text-[13px] transition-colors duration-500";

export function Links({ pathname }: { pathname: string }) {
  const home = pathname === "/";
  const settings = pathname.startsWith("/settings");
  return (
    <>
      <Link href="/" aria-current={home ? "page" : undefined} className={cn(item, "px-2 py-1 sm:px-3", home ? "bg-primary/10 font-medium text-primary" : "text-muted-foreground hover:text-foreground")}>
        <span className="sm:hidden">New</span>
        <span className="hidden sm:inline">New analysis</span>
      </Link>
      <UsageMenu />
      <HowItWorksButton />
      <Link href="/settings" aria-label="Settings" aria-current={settings ? "page" : undefined} className={cn(item, "grid size-8 place-items-center sm:size-9", settings ? "bg-primary/10 text-primary" : "text-muted-foreground hover:text-foreground")}>
        <Settings className="size-4" strokeWidth={1.75} />
      </Link>
    </>
  );
}

/** Needs the current path, which only exists at request time — so it must sit inside <Suspense>. */
export function NavLinks() {
  return <Links pathname={usePathname()} />;
}
