"use client";

import { TriangleAlert } from "lucide-react";
import Link from "next/link";
import { useParams, usePathname } from "next/navigation";
import { useEffect, useState } from "react";

import { BackLink } from "@/components/back-link";
import { BrandLogo } from "@/components/brand-logo";
import { PlatformIcon } from "@/components/platform-icon";
import { buttonVariants } from "@/components/ui/button";
import { InfoTip } from "@/components/ui/info-tip";
import { WizardStepper } from "@/components/wizard-stepper";
import { analysisTitle, sourceLabels } from "@/lib/analysis-title";
import { usd } from "@/lib/format";
import { settingsApi } from "@/lib/settings-api";
import { cn } from "@/lib/utils";
import { type StepKey, activeStep } from "@/lib/steps";

import { AnalysisContext } from "./context";
import { useAnalysis } from "./use-analysis";

/** What this analysis has spent, in the unit each provider bills: Apify credits (with what's left) and model usage. */
function Spend({ apifyUsd, llmUsd, llmKnown, model }: { apifyUsd: number; llmUsd: number; llmKnown: boolean; model: string | null }) {
  const [left, setLeft] = useState<number | null>(null);
  useEffect(() => {
    settingsApi.testApify().then((a) => setLeft(a.remaining_usd)).catch(() => setLeft(null));
  }, [apifyUsd]);
  return (
    <InfoTip label="What this analysis cost" text="Cost">
      <span>
        <strong className="font-medium">Apify credits</strong> used {usd(apifyUsd)}
        {left != null && <>, {usd(left)} left this month</>}
      </span>
      {model && (
        <span>
          <strong className="font-medium">Model</strong> {model}
          {llmKnown ? ` · ${usd(llmUsd)}` : ""}
        </span>
      )}
      <span className="opacity-70">Apify pays for the Facebook reads. The model is billed separately by its provider.</span>
    </InfoTip>
  );
}

const BACK: Record<StepKey, { label: string; href: (id: string) => string }> = {
  brand: { label: "Back to home", href: () => "/" },
  profile: { label: "Back to home", href: () => "/" },
  search: { label: "Back to profile", href: (id) => `/analysis/${id}` },
  creators: { label: "Back to search", href: (id) => `/analysis/${id}/search` },
};

/** One creator's page sits under the list, so going back leads to the list, not further. */
function backTarget(pathname: string, id: string, step: StepKey) {
  return /\/creators\/[^/]+$/.test(pathname) ? { label: "Back to creators", href: `/analysis/${id}/creators` } : { label: BACK[step].label, href: BACK[step].href(id) };
}

/** Frame shared by every step of an analysis: who it's about, where you are, what it has cost so far. */
export function AnalysisShell({ children }: { children: React.ReactNode }) {
  const { id } = useParams<{ id: string }>();
  const pathname = usePathname();
  const { analysis, error, adopt } = useAnalysis(id);

  if (error) {
    return (
      <div className="flex flex-col items-start gap-4 pt-10">
        <p className="text-destructive" role="alert">
          {error}
        </p>
        <Link href="/" className={buttonVariants()}>
          New analysis
        </Link>
      </div>
    );
  }
  if (!analysis) return <p className="pt-10 text-muted-foreground">Loading…</p>;

  const title = analysisTitle(analysis);

  return (
    <AnalysisContext.Provider value={{ analysis, adopt }}>
      <div className={cn("mx-auto flex w-full flex-col gap-8 pt-4 transition-[max-width] duration-500", pathname.endsWith("/creators") ? "max-w-6xl" : "max-w-4xl")}>
        <BackLink {...backTarget(pathname, analysis.id, activeStep(pathname, analysis))} className="-mb-4" />
        <header className="flex flex-wrap items-start justify-between gap-x-6 gap-y-4">
          <div className="flex min-w-0 items-center gap-4">
            <BrandLogo id={analysis.id} hasLogo={analysis.has_logo} name={title} className="size-14 text-2xl" />
            <div className="min-w-0">
              <h1 className="truncate font-heading text-2xl font-semibold tracking-tight sm:text-3xl">{title}</h1>
              <p className="flex flex-wrap items-center gap-x-3 text-sm text-muted-foreground">
                {sourceLabels(analysis).map((s) => (
                  <span key={s.label} className="flex min-w-0 items-center gap-1.5 truncate">
                    <PlatformIcon platform={s.platform} className="size-3.5" /> {s.value}
                  </span>
                ))}
                <Spend apifyUsd={analysis.cost.apify_usd} llmUsd={analysis.cost.llm_usd} llmKnown={analysis.cost.llm_known} model={analysis.cost.llm_model} />
              </p>
            </div>
          </div>
          <WizardStepper analysis={analysis} active={activeStep(pathname, analysis)} />
        </header>

        {analysis.warnings.map((w) => (
          <p key={w} className="flex items-start gap-2 rounded-2xl bg-amber-50 px-4 py-3 text-sm text-amber-800 ring-1 ring-amber-200">
            <TriangleAlert className="mt-0.5 size-4 shrink-0" strokeWidth={1.75} /> {w}
          </p>
        ))}

        {children}
      </div>
    </AnalysisContext.Provider>
  );
}
