import Link from "next/link";
import { Suspense } from "react";

import { Links, NavLinks } from "./nav-links";

/** Small and quiet on purpose, and part of the page (not floating over it), so it never covers content. */
export function AppHeader() {
  return (
    <header className="flex items-center justify-between gap-3 px-4 pt-3 sm:px-6">
      <Link href="/" className="flex items-center gap-1.5 font-heading text-[15px] font-semibold tracking-tight">
        <span aria-hidden className="size-2.5 rounded-full bg-primary" />
        SmartKOL
      </Link>
      <nav aria-label="Main" className="flex items-center gap-0.5 rounded-full bg-white/80 p-1 ring-1 ring-black/[0.05]">
        <Suspense fallback={<Links pathname="" />}>
          <NavLinks />
        </Suspense>
      </nav>
    </header>
  );
}
