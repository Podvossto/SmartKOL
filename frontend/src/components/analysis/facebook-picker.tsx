"use client";

import { Check, ExternalLink, TriangleAlert } from "lucide-react";
import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { PillButton } from "@/components/ui/pill-button";
import { type Analysis, type Candidate, analysisApi } from "@/lib/analysis-api";
import { errorMessage } from "@/lib/errors";
import { formatCount, timeAgo } from "@/lib/format";
import { cn } from "@/lib/utils";

type Choice = { kind: "page"; url: string } | { kind: "paste" } | { kind: "none" };

// Initials only: Facebook's picture URLs are signed, expire quickly and block hotlinking, and loading them
// would make every viewer's browser contact Facebook.
function Avatar({ candidate }: { candidate: Candidate }) {
  return (
    <span className="grid size-10 shrink-0 place-items-center rounded-xl bg-accent font-medium text-accent-foreground">
      {(candidate.title ?? "?").charAt(0).toUpperCase()}
    </span>
  );
}

const optionClass = (selected: boolean, disabled = false) =>
  cn(
    "relative flex gap-4 rounded-3xl bg-card p-5 ring-1 transition-all duration-500 ease-[cubic-bezier(0.32,0.72,0,1)]",
    selected ? "ring-2 ring-primary shadow-[0_16px_36px_-18px_rgba(20,60,200,0.45)]" : "ring-black/[0.07] hover:ring-primary/40",
    disabled ? "cursor-not-allowed opacity-60" : "cursor-pointer",
  );

function Tick({ on }: { on: boolean }) {
  return (
    <span aria-hidden className={cn("absolute right-5 top-5 grid size-6 place-items-center rounded-full transition-all duration-500", on ? "bg-primary text-primary-foreground" : "border border-border bg-white")}>
      {on && <Check className="size-3.5" strokeWidth={3} />}
    </span>
  );
}

function CandidateCard({ candidate, selected, recommended, onSelect }: { candidate: Candidate; selected: boolean; recommended: boolean; onSelect: () => void }) {
  return (
    <label className={optionClass(selected, !candidate.readable)}>
      <input type="radio" name="facebook-page" className="sr-only" checked={selected} disabled={!candidate.readable} onChange={onSelect} />
      <Tick on={selected} />
      <Avatar candidate={candidate} />
      <div className="flex min-w-0 flex-1 flex-col gap-2 pr-8">
        <div className="flex flex-wrap items-center gap-2">
          <span className="font-medium">{candidate.title ?? "Unreadable page"}</span>
          {recommended && <Badge>Recommended</Badge>}
          <Badge variant="outline">{candidate.source === "provided" ? "You provided this" : "Linked from the website"}</Badge>
        </div>
        {candidate.readable && (
          <p className="text-sm text-muted-foreground">
            {[candidate.category, candidate.address, `${formatCount(candidate.followers)} followers`, `last post ${timeAgo(candidate.last_post_at)}`].filter(Boolean).join(" · ")}
          </p>
        )}
        {candidate.warnings.map((w) => (
          <p key={w} className="flex items-start gap-1.5 text-sm text-amber-700">
            <TriangleAlert className="mt-0.5 size-3.5 shrink-0" strokeWidth={1.75} /> {w}
          </p>
        ))}
        <a href={candidate.url} target="_blank" rel="noreferrer" className="flex w-fit items-center gap-1 text-xs text-primary underline-offset-4 hover:underline" onClick={(e) => e.stopPropagation()}>
          Open on Facebook <ExternalLink className="size-3" strokeWidth={1.75} />
        </a>
      </div>
    </label>
  );
}

export function FacebookPicker({ analysis, onAdopt }: { analysis: Analysis; onAdopt: (a: Analysis) => void }) {
  const candidates = analysis.facebook_candidates;
  const [choice, setChoice] = useState<Choice>(analysis.recommended ? { kind: "page", url: analysis.recommended } : { kind: "none" });
  const [pasted, setPasted] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const canContinue = choice.kind !== "paste" || pasted.trim().length > 0;

  async function confirm() {
    setBusy(true);
    setError(null);
    try {
      const url = choice.kind === "page" ? choice.url : choice.kind === "paste" ? pasted.trim() : null;
      onAdopt(await analysisApi.confirmFacebook(analysis.id, url));
    } catch (err) {
      setError(errorMessage(err));
      setBusy(false);
    }
  }

  return (
    <div className="animate-rise flex flex-col gap-7">
      <div className="flex flex-col gap-2">
        <h2 className="font-heading text-2xl font-semibold tracking-tight text-balance">Which Facebook page is theirs?</h2>
        <p className="max-w-2xl text-muted-foreground">
          {candidates.length > 0 ? "Found on the website. Brands often link regional or old pages, so check first." : "None found on the website. Paste its link, or continue without."}
        </p>
      </div>

      <div className="flex flex-col gap-3" role="radiogroup" aria-label="Facebook page">
        {candidates.map((c) => (
          <CandidateCard key={c.url} candidate={c} recommended={c.url === analysis.recommended} selected={choice.kind === "page" && choice.url === c.url} onSelect={() => setChoice({ kind: "page", url: c.url })} />
        ))}

        <label className={cn(optionClass(choice.kind === "paste"), "flex-col gap-3")}>
          <Tick on={choice.kind === "paste"} />
          <span className="flex items-center gap-3 text-sm font-medium">
            <input type="radio" name="facebook-page" className="sr-only" checked={choice.kind === "paste"} onChange={() => setChoice({ kind: "paste" })} />
            Use a different page
          </span>
          {choice.kind === "paste" && <Input autoFocus placeholder="https://www.facebook.com/yourbrand" value={pasted} onChange={(e) => setPasted(e.target.value)} aria-label="Facebook page link" />}
        </label>

        <label className={cn(optionClass(choice.kind === "none"), "items-center text-sm font-medium")}>
          <Tick on={choice.kind === "none"} />
          <input type="radio" name="facebook-page" className="sr-only" checked={choice.kind === "none"} onChange={() => setChoice({ kind: "none" })} />
          Continue without Facebook <span className="font-normal text-muted-foreground">(website only)</span>
        </label>
      </div>

      {error && (
        <p className="text-sm text-destructive" role="alert">
          {error}
        </p>
      )}
      <PillButton className="self-start" onClick={confirm} loading={busy} disabled={!canContinue}>
        {busy ? "Starting…" : "Build brand profile"}
      </PillButton>
    </div>
  );
}
