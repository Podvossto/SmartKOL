"use client";

import Link from "next/link";

import { buttonVariants } from "@/components/ui/button";

import { useCurrentAnalysis } from "./context";
import { CreatorSearch } from "./creator-search";
import { EmptyState, Rise } from "./panel";
import { SearchMethod } from "./search-method";
import { SearchPlan } from "./search-plan";

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
        <p className="text-muted-foreground">Check the hashtags, choose how many videos to read from each, then run the search.</p>
      </Rise>
      <Rise index={1}>
        <SearchPlan />
      </Rise>
      <Rise index={2}>
        <CreatorSearch />
      </Rise>
      <Rise index={3}>
        <SearchMethod />
      </Rise>
    </div>
  );
}
