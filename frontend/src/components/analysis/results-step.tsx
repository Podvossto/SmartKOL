"use client";

import Link from "next/link";

import { buttonVariants } from "@/components/ui/button";

import { useCurrentAnalysis } from "./context";
import { EmptyState } from "./panel";

export function ResultsStep() {
  const { analysis } = useCurrentAnalysis();
  return (
    <EmptyState title="No creators yet" text="Ranked creators will appear here once a search has run.">
      <Link href={`/analysis/${analysis.id}/creators`} className={buttonVariants()}>
        Go to creators
      </Link>
    </EmptyState>
  );
}
