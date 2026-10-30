"use client";

import Link from "next/link";

import { buttonVariants } from "@/components/ui/button";
import { PillButton } from "@/components/ui/pill-button";

import { PlatformIcon } from "@/components/platform-icon";

import { useCurrentAnalysis } from "./context";
import { EmptyState, Rise } from "./panel";
import { SearchMethod } from "./search-method";
import { SearchPlan } from "./search-plan";

/** Where the creator search plugs in: review the plan, then (next release) run it and watch the cost. */
function SearchRun() {
  return (
    <div className="flex flex-wrap items-center justify-between gap-4 rounded-3xl bg-white/70 px-6 py-5 ring-1 ring-black/[0.05]">
      <div>
        <p className="flex items-center gap-2 font-medium">
          <PlatformIcon platform="tiktok" /> Search TikTok
        </p>
        <p className="text-sm text-muted-foreground">The estimated cost will show here before anything runs.</p>
      </div>
      <PillButton disabled title="Creator search arrives in the next release">
        Search creators
      </PillButton>
    </div>
  );
}

export function CreatorsStep() {
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
        <p className="text-muted-foreground">Check what to search for, then run the search.</p>
      </Rise>
      <Rise index={1}>
        <SearchPlan />
      </Rise>
      <Rise index={2}>
        <SearchRun />
      </Rise>
      <Rise index={3}>
        <SearchMethod />
      </Rise>
    </div>
  );
}
