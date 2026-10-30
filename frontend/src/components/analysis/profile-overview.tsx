"use client";

import { Check, X } from "lucide-react";
import { useRouter } from "next/navigation";

import { PlatformIcon } from "@/components/platform-icon";
import { Disclosure } from "@/components/ui/disclosure";
import { PillButton } from "@/components/ui/pill-button";
import type { Profile } from "@/lib/analysis-api";
import { STEPS } from "@/lib/steps";
import { cn } from "@/lib/utils";

import { BrandBanner, BrandGallery } from "./brand-media";
import { useCurrentAnalysis } from "./context";
import { IdealCreator } from "./ideal-creator";
import { Origin } from "./origin";
import { ChipList, Eyebrow, FactRow, Rise } from "./panel";
import { SourceDetails } from "./source-details";

const TIER_LABEL = { budget: "Budget", mid: "Mid-range", premium: "Premium", unknown: "" } as const;
const PERFORMANCE = {
  strong: { label: "Performs well", tone: "text-emerald-700" },
  average: { label: "Average", tone: "text-muted-foreground" },
  weak: { label: "Weaker", tone: "text-amber-700" },
  unknown: null,
} as const;
const brief = (item: string) => item.split(" (")[0]; // "Matcha drinks (A, B, C)" -> "Matcha drinks"
const list = (items: string[]) => items.join(" · "); // a middle dot, because the items themselves may contain commas
/** "18-34" alone is just numbers to a reader: say what they are. */
const age = (range: string) => (!known(range) ? "" : /^[\d\s–—-]+\+?$/.test(range.trim()) ? `Age ${range.trim()}` : range.trim());
const gender = (value: string) => (!known(value) ? "" : value.trim().charAt(0).toUpperCase() + value.trim().slice(1));
const known = (text: string) => !/^(not stated|unknown|n\/a)/i.test(text.trim()); // older profiles hold a placeholder instead of an estimate

/** One item per line, for entries that are phrases (they may contain commas, so a comma-joined list would blur them). */
function Lines({ items }: { items: string[] }) {
  return (
    <ul className="flex flex-col gap-1">
      {items.map((item) => (
        <li key={item}>{item}</li>
      ))}
    </ul>
  );
}

/** A section of the brief: small title, then its content. The whole brief is marked as AI-written once, at the top. */
function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="flex flex-col gap-3">
      <Eyebrow>{title}</Eyebrow>
      {children}
    </div>
  );
}

function Rules({ title, items, kind }: { title: string; items: string[]; kind: "do" | "dont" }) {
  const Icon = kind === "do" ? Check : X;
  return (
    <div className="flex flex-col gap-2">
      <p className="text-sm font-medium">{title}</p>
      <ul className="flex flex-col gap-1.5 text-sm">
        {items.map((item) => (
          <li key={item} className="flex gap-2">
            <Icon className={cn("mt-0.5 size-4 shrink-0", kind === "do" ? "text-emerald-600" : "text-destructive")} strokeWidth={2} />
            <span>{item}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

function FullProfile({ profile }: { profile: Profile }) {
  const block = (title: string, body: React.ReactNode) => (
    <div className="flex flex-col gap-2.5">
      <Eyebrow>{title}</Eyebrow>
      {body}
    </div>
  );
  return (
    <>
      {block("Products & services", <Lines items={profile.products} />)}
      {block("Audience persona", <>
        <p className="text-[15px]">{profile.audience.description}</p>
        <p className="text-sm text-muted-foreground">{profile.audience.lifestyle}</p>
        <ChipList items={profile.audience.interests} />
        {profile.audience.media_habits.length > 0 && <p className="text-sm text-muted-foreground">Media habits: {list(profile.audience.media_habits)}</p>}
      </>)}
      {(profile.voice.style || profile.voice.dos.length > 0 || profile.voice.donts.length > 0) &&
        block("Voice guidelines", <>
          {profile.voice.style && <p className="text-[15px]">{profile.voice.style}</p>}
          {(profile.voice.dos.length > 0 || profile.voice.donts.length > 0) && (
            <div className="grid gap-5 sm:grid-cols-2">
              <Rules title="Do" items={profile.voice.dos} kind="do" />
              <Rules title="Don't" items={profile.voice.donts} kind="dont" />
            </div>
          )}
        </>)}
      {profile.formats.length > 0 && block("Content formats", <ChipList items={profile.formats} />)}
      {profile.evidence.length > 0 &&
        block("What this is based on", (
          <ul className="flex flex-col gap-2 text-sm">
            {profile.evidence.map((e) => (
              <li key={e.fact} className="flex gap-2.5">
                <span className="mt-0.5 flex shrink-0 gap-1">
                  {e.source !== "facebook" && <PlatformIcon platform="website" className="size-3.5" />}
                  {e.source !== "website" && <PlatformIcon platform="facebook" className="size-3.5" />}
                </span>
                <span>{e.fact}</span>
              </li>
            ))}
          </ul>
        ))}
      {profile.gaps.length > 0 &&
        block("Not found in the sources", (
          <ul className="flex flex-col gap-1.5 text-sm text-muted-foreground">
            {profile.gaps.map((gap) => (
              <li key={gap} className="flex gap-2.5">
                <span aria-hidden className="mt-2 size-1.5 shrink-0 rounded-full bg-amber-400" />
                <span>{gap}</span>
              </li>
            ))}
          </ul>
        ))}
    </>
  );
}

export function ProfileOverview() {
  const router = useRouter();
  const { analysis } = useCurrentAnalysis();
  const profile = analysis.profile as Profile;
  const model = analysis.cost.llm_model;
  const sources = (["website", "facebook"] as const).filter((s) => profile.by_source[s]);
  const tier = TIER_LABEL[profile.price_tier];
  const banner = analysis.media.find((m) => m.role === "banner");
  const samples = analysis.media.filter((m) => m.role === "sample");
  const fit = profile.creator_fit;

  return (
    <div className="flex flex-col gap-8">
      {banner && (
        <Rise>
          <BrandBanner analysisId={analysis.id} item={banner} />
        </Rise>
      )}

      <Rise className="relative z-20 flex flex-wrap items-center gap-x-3 gap-y-1 text-sm text-muted-foreground">
        <Origin kind="ai" model={model} />
        <span>The brief below is written by the model from your sources. Items marked &ldquo;From source&rdquo; are read as-is.</span>
      </Rise>

      <Rise>
        <Section title="Overview">
          <p className="flex flex-wrap items-center gap-2 text-sm text-muted-foreground">
            <span className="rounded-full bg-primary/10 px-2.5 py-0.5 font-medium text-primary">{profile.category}</span>
            {tier && <span>{tier}</span>}
          </p>
          {profile.positioning && <p className="max-w-3xl text-xl font-medium leading-snug tracking-tight text-balance">{profile.positioning}</p>}
          <p className="max-w-3xl text-base leading-relaxed text-foreground/80">{profile.summary}</p>
        </Section>
      </Rise>

      <Rise index={1}>
        <Section title="Key attributes">
          <dl className="divide-y divide-border/70 rounded-3xl bg-white/70 ring-1 ring-black/[0.05]">
            <FactRow label="Products & services">{list(profile.products.map(brief))}</FactRow>
            <FactRow label="Audience">
              {[age(profile.audience.age_range), gender(profile.audience.gender)].filter(Boolean).length > 0 && <span>{[age(profile.audience.age_range), gender(profile.audience.gender)].filter(Boolean).join(" · ")}</span>}
              <span className="text-muted-foreground">Interested in {list(profile.audience.interests)}</span>
            </FactRow>
            <FactRow label="Tone of voice">{list(profile.voice.traits)}</FactRow>
          </dl>
        </Section>
      </Rise>

      {profile.pillars.length > 0 && (
        <Rise index={2}>
          <Section title="Content pillars">
            <ul className="divide-y divide-border/70 rounded-3xl bg-white/70 ring-1 ring-black/[0.05]">
              {profile.pillars.map((pillar) => {
                const perf = PERFORMANCE[pillar.performance];
                return (
                  <li key={pillar.theme} className="flex flex-col gap-1 px-6 py-4 sm:flex-row sm:items-baseline sm:justify-between sm:gap-6">
                    <div className="min-w-0">
                      <p className="font-medium">{pillar.theme}</p>
                      {pillar.detail && <p className="text-sm text-muted-foreground">{pillar.detail}</p>}
                    </div>
                    {perf && <span className={cn("shrink-0 text-xs font-medium", perf.tone)}>{perf.label}</span>}
                  </li>
                );
              })}
            </ul>
          </Section>
        </Rise>
      )}

      {fit.niches.length > 0 && (
        <Rise index={3}>
          <IdealCreator />
        </Rise>
      )}

      {samples.length > 0 && (
        <Rise index={4}>
          <BrandGallery analysisId={analysis.id} items={samples} />
        </Rise>
      )}

      <Rise index={5} className="flex flex-col gap-3">
        <Disclosure title="Full brand profile" hint="persona, voice guidelines, evidence, gaps">
          <FullProfile profile={profile} />
        </Disclosure>
        <Disclosure title="Sources" hint={sources.length > 1 ? "website and Facebook, side by side" : sources[0] === "website" ? "website" : "Facebook"}>
          <SourceDetails analysis={analysis} />
        </Disclosure>
      </Rise>

      <Rise index={6} className="flex flex-wrap items-center justify-between gap-4 border-t border-border/70 pt-6">
        <p className="text-sm text-muted-foreground">Next: choose the hashtags to search on TikTok.</p>
        <PillButton onClick={() => router.push(STEPS.find((s) => s.key === "search")!.href(analysis.id))}>Continue to search</PillButton>
      </Rise>
    </div>
  );
}
