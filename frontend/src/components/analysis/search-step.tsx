"use client";

import Link from "next/link";

import { buttonVariants } from "@/components/ui/button";
import { PillButton } from "@/components/ui/pill-button";
import { STEPS } from "@/lib/steps";
import { useRouter } from "next/navigation";

import { useCurrentAnalysis } from "./context";
import { CreatorSearch } from "./creator-search";
import { EmptyState, Rise } from "./panel";
import { SearchMethod } from "./search-method";
import { SearchPlan } from "./search-plan";

/** Search found people: the way on is to look at them, so it is offered right under the search. */
function FoundCta() {
  const { analysis } = useCurrentAnalysis();
  const router = useRouter();
  if (analysis.creators.status !== "done" || analysis.creators.found === 0) return null;
  return (
    <div className="flex flex-wrap items-center justify-between gap-4 rounded-3xl bg-primary/[0.06] px-6 py-5 ring-1 ring-primary/20">
      <div>
        <p className="font-medium">{analysis.creators.found} creators found</p>
        <p className="text-sm text-muted-foreground">From {analysis.creators.videos} videos under {analysis.creators.hashtags.length} hashtags. Filter and compare them on the next page.</p>
      </div>
      <PillButton onClick={() => router.push(STEPS.find((s) => s.key === "creators")!.href(analysis.id))}>View creators</PillButton>
    </div>
  );
}

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
        <p className="text-muted-foreground">Check what to search for, choose a budget, then run the search.</p>
      </Rise>
      <Rise index={1}>
        <SearchPlan />
      </Rise>
      <Rise index={2}>
        <CreatorSearch />
      </Rise>
      <Rise index={3}>
        <FoundCta />
      </Rise>
      <Rise index={4}>
        <SearchMethod />
      </Rise>
    </div>
  );
}
