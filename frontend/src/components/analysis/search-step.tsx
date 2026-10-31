"use client";

import Link from "next/link";

import { buttonVariants } from "@/components/ui/button";

import { useCurrentAnalysis } from "./context";
import { CreatorSearch } from "./creator-search";
import { EmptyState, Rise } from "./panel";
import { SearchMethod } from "./search-method";

export function SearchStep() {
  const { analysis } = useCurrentAnalysis();
  if (!analysis.profile) {
    return (
      <EmptyState title="Finish the brand profile first" text="Creators are matched against the profile, so it has to exist before searching.">
        <Link href={`/analysis/${analysis.id}`} className={buttonVariants({ variant: "outline" })}>
          Back to the brand
        </Link>
      </EmptyState>
    );
  }
  return (
    <div className="flex flex-col gap-6">
      <Rise>
        <h2 className="font-heading text-2xl font-semibold tracking-tight">Find creators</h2>
        <p className="text-muted-foreground">Pick the hashtags to search. Nothing is spent until you press search.</p>
      </Rise>
      <Rise index={1}>
        <CreatorSearch />
      </Rise>
      <Rise index={2}>
        <SearchMethod />
      </Rise>
    </div>
  );
}
