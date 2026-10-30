import { Suspense } from "react";

import { AnalysisShell } from "@/components/analysis/shell";

export default function AnalysisLayout({ children }: { children: React.ReactNode }) {
  return (
    <main className="mx-auto w-full max-w-4xl flex-1 px-4 pb-20">
      <Suspense fallback={<p className="pt-10 text-muted-foreground">Loading…</p>}>
        <AnalysisShell>{children}</AnalysisShell>
      </Suspense>
    </main>
  );
}
