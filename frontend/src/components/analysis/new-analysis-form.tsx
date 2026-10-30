"use client";

import { ChevronDown, Plus, Search, X } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState, useTransition } from "react";

import { PlatformIcon } from "@/components/platform-icon";
import { Collapse } from "@/components/ui/collapse";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { Input } from "@/components/ui/input";
import { PillButton } from "@/components/ui/pill-button";
import { type Estimate, type RecentItem, analysisApi } from "@/lib/analysis-api";
import { errorMessage } from "@/lib/errors";
import { timeAgo, usd } from "@/lib/format";
import { ApiError } from "@/lib/http";
import { kindOf, linkKey, linkProblem } from "@/lib/links";
import { type SettingsView, settingsApi } from "@/lib/settings-api";
import { cn } from "@/lib/utils";

/** A quick side-to-side shake, to say "this one" without a word. Skipped for people who ask for less motion. */
function shake(el: HTMLElement | null | undefined) {
  if (!el || window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
  el.animate([{ transform: "translateX(0)" }, { transform: "translateX(-8px)" }, { transform: "translateX(7px)" }, { transform: "translateX(-5px)" }, { transform: "translateX(3px)" }, { transform: "translateX(0)" }], { duration: 420, easing: "ease-out" });
}

function LinkField({
  value,
  onChange,
  onBlur,
  placeholder,
  label,
  error,
  large,
  onRemove,
  index,
}: {
  value: string;
  onChange: (v: string) => void;
  onBlur: () => void;
  placeholder: string;
  label: string;
  error?: string;
  large?: boolean;
  onRemove?: () => void;
  index: number;
}) {
  const kind = value.trim() ? kindOf(value) : "website";
  return (
    <div data-field={index} className="flex flex-col">
      <div className="relative">
        <span key={kind} className={cn("pointer-events-none absolute left-5 top-1/2 -translate-y-1/2", kind === "facebook" && "animate-pop")}>
          <PlatformIcon platform={kind} className="size-[18px]" />
        </span>
        <Input
          aria-label={label}
          aria-invalid={error ? true : undefined}
          placeholder={placeholder}
          value={value}
          autoComplete="off"
          spellCheck={false}
          onChange={(e) => onChange(e.target.value)}
          onBlur={onBlur}
          className={cn("rounded-full pl-12 text-base", onRemove && "pr-12", large ? "h-14 shadow-[0_10px_30px_-14px_rgba(20,40,120,0.3)]" : "h-12", kind === "facebook" && !error && "focus-visible:border-[#1877F2] focus-visible:ring-[#1877F2]/25")}
        />
        {onRemove && (
          <button type="button" onClick={onRemove} aria-label="Remove this link" className="absolute right-3 top-1/2 grid size-7 -translate-y-1/2 place-items-center rounded-full text-muted-foreground transition-colors hover:bg-black/[0.05] hover:text-foreground">
            <X className="size-4" strokeWidth={1.75} />
          </button>
        )}
      </div>
      <Collapse open={!!error}>
        <p role={error ? "alert" : undefined} className="px-4 pt-2 text-sm text-destructive">
          {error}
        </p>
      </Collapse>
    </div>
  );
}

/** One short line about cost, with the rest one click away. */
function CostLine({ estimate, state, settings }: { estimate: Estimate | null; state: "loading" | "ready" | "failed"; settings: SettingsView | null }) {
  const [open, setOpen] = useState(false);
  const apify = estimate?.apify;
  const left = estimate?.account?.remaining_usd;
  const free = !!apify && apify.high_usd === 0 && !apify.cached;
  const price = !apify ? null : apify.cached ? "$0 (already read, from cache)" : free ? "Free" : apify.low_usd === apify.high_usd ? `≈ ${usd(apify.low_usd)}` : `${usd(apify.low_usd)} – ${usd(apify.high_usd)}`;
  const short = apify && left != null && apify.high_usd > left;
  return (
    <div className="flex flex-col gap-2 px-4 text-sm">
      <button type="button" aria-expanded={open} onClick={() => setOpen(!open)} className="flex w-fit items-center gap-1.5 text-left text-muted-foreground transition-colors hover:text-foreground">
        <span>
          {state === "failed" ? (
            "Couldn't estimate the cost"
          ) : state === "loading" || !price ? (
            "Checking the cost…"
          ) : free ? (
            <>
              <span className="font-medium text-foreground">No Apify credits</span> needed · the language model is billed by your provider
            </>
          ) : (
            <>
              <span className="font-medium text-foreground">{price}</span> of Apify credits
            </>
          )}
          {left != null && <> · {usd(left)} left</>}
        </span>
        <ChevronDown className={`size-3.5 shrink-0 transition-transform duration-500 ease-[cubic-bezier(0.32,0.72,0,1)] ${open ? "rotate-180" : ""}`} strokeWidth={1.75} />
      </button>
      <Collapse open={open}>
        <ul className="flex flex-col gap-1 pb-1 text-muted-foreground">
          {apify && <li>{apify.note}.</li>}
          {left != null && estimate?.account && (
            <li>
              {usd(left)} of {usd(estimate.account.limit_usd)} Apify credits left this month.
            </li>
          )}
          <li>Language model: {estimate?.llm?.model ?? settings?.llm.model ?? "not set"}, billed by your provider, not Apify. Writing one brief cost about $0.003 in our runs.</li>
        </ul>
      </Collapse>
      {short && <p className="font-medium text-destructive">This may need more credits than you have left.</p>}
    </div>
  );
}

export function NewAnalysisForm() {
  const router = useRouter();
  const [settings, setSettings] = useState<SettingsView | null>(null);
  const [links, setLinks] = useState(["", ""]);
  const [second, setSecond] = useState(false);
  const [findFb, setFindFb] = useState(false);
  const [result, setResult] = useState<{ key: string; estimate: Estimate | null } | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [opening, startOpening] = useTransition(); // true until the new page is on screen, and false again when you come back
  const [errors, setErrors] = useState<Record<number, string>>({});
  const [formError, setFormError] = useState<string | null>(null);
  const [duplicate, setDuplicate] = useState<RecentItem | null>(null);
  const form = useRef<HTMLFormElement>(null);
  const fieldBox = (i: number) => form.current?.querySelector<HTMLElement>(`[data-field="${i}"]`);
  const busy = submitting || opening;

  useEffect(() => {
    settingsApi.get().then(setSettings).catch(() => setSettings(null));
  }, []);

  // Which link is the website and which the Facebook page is read from the link itself.
  const entries = links.map((raw, index) => ({ index, raw: raw.trim(), kind: kindOf(raw) })).filter((e) => e.raw && (second || e.index === 0) && !linkProblem(e.raw));
  const site = entries.find((e) => e.kind === "website");
  const fb = entries.find((e) => e.kind === "facebook");
  const twins = entries.length === 2 && !site !== !fb; // two links of the same kind
  const siteUrl = site?.raw ?? "";
  const fbUrl = fb?.raw ?? "";
  const find = findFb && !!siteUrl && !fbUrl;
  const conflict = twins ? `Both links look like ${entries[0].kind === "facebook" ? "Facebook pages" : "websites"}. Use one of each, or just one link.` : null;

  // The cost is for one exact set of inputs; until the answer for the current ones arrives it is "loading".
  const key = [siteUrl, fbUrl, find].join("|");
  useEffect(() => {
    // Refresh the cost a moment after typing stops; free to call, nothing paid runs.
    const timer = setTimeout(
      () => {
        analysisApi
          .estimate(siteUrl, fbUrl, find)
          .then((estimate) => setResult({ key, estimate }))
          .catch(() => setResult({ key, estimate: null }));
      },
      siteUrl || fbUrl ? 450 : 0,
    );
    return () => clearTimeout(timer);
  }, [key, siteUrl, fbUrl, find]);
  const estimate = result?.estimate ?? null;
  const estimateState = result?.key !== key ? "loading" : result.estimate ? "ready" : "failed";

  const missing = settings ? [!settings.apify.configured && (fbUrl || find) && "an Apify token", !settings.llm.configured && "a language model"].filter(Boolean) : [];
  const credits = estimate?.account?.remaining_usd;
  const tooExpensive = estimateState === "ready" && !!(estimate?.apify && credits != null && estimate.apify.high_usd > credits);
  const setLink = (index: number, value: string) => {
    setLinks((current) => current.map((l, i) => (i === index ? value : l)));
    setErrors((current) => (current[index] ? { ...current, [index]: "" } : current));
    setFormError(null);
  };
  const closeSecond = () => {
    setSecond(false);
    setFindFb(false);
    setLink(1, "");
    setErrors({});
  };
  const checkOnLeave = (index: number) => () => {
    const problem = linkProblem(links[index]);
    if (problem) setErrors((current) => ({ ...current, [index]: problem }));
  };

  /** Everything that can be checked without the server. Shakes and focuses what needs fixing; true when all is well. */
  function validate(): boolean {
    const found: Record<number, string> = {};
    if (!links[0].trim()) found[0] = "Paste a website or Facebook page link to begin.";
    else {
      const problem = linkProblem(links[0]);
      if (problem) found[0] = problem;
    }
    if (second && !findFb) {
      if (!links[1].trim()) found[1] = "Add the second link, or remove it.";
      else {
        const problem = linkProblem(links[1]);
        if (problem) found[1] = problem;
      }
    }
    setErrors(found);
    const bad = Object.keys(found).map(Number);
    if (bad.length) {
      bad.forEach((i) => shake(fieldBox(i)));
      fieldBox(bad[0])?.querySelector("input")?.focus();
      return false;
    }
    const blocker = conflict ?? (missing.length ? `Add ${missing.join(" and ")} in Settings first.` : tooExpensive ? "This may need more credits than you have left." : null);
    if (blocker) {
      setFormError(blocker);
      requestAnimationFrame(() => shake(form.current?.querySelector<HTMLElement>("[data-banner]")));
      return false;
    }
    return true;
  }

  async function start() {
    setDuplicate(null);
    setSubmitting(true);
    setErrors({});
    setFormError(null);
    try {
      const created = await analysisApi.start(siteUrl, fbUrl, find);
      startOpening(() => router.push(`/analysis/${created.id}`));
    } catch (err) {
      const field = err instanceof ApiError ? err.field : null;
      const owner = field === "website_url" ? site : field === "facebook_url" ? fb : null;
      if (owner) {
        setErrors({ [owner.index]: errorMessage(err) });
        shake(fieldBox(owner.index));
      } else setFormError(errorMessage(err));
    } finally {
      setSubmitting(false);
    }
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (busy || !validate()) return;
    // Same brand as one already analysed? Say so before spending anything.
    const keys = entries.map((en) => linkKey(en.raw)).filter((k) => !!k);
    const recent = await analysisApi.recent().catch(() => []);
    const same = recent.find((r) => r.status !== "error" && keys.some((k) => (k.kind === "website" ? r.website === k.key : r.facebook?.toLowerCase() === k.key)));
    if (same) setDuplicate(same);
    else await start();
  }

  const firstIsFacebook = kindOf(links[0]) === "facebook";

  return (
    <form ref={form} onSubmit={submit} className="flex flex-col gap-4" noValidate>
      {missing.length > 0 && (
        <p className="rounded-2xl bg-accent px-4 py-3 text-sm" role="status">
          Before you start, add {missing.join(" and ")} in{" "}
          <Link href="/settings" className="font-medium text-primary underline-offset-4 hover:underline">
            Settings
          </Link>
          .
        </p>
      )}

      <LinkField large index={0} label="Website or Facebook page" placeholder="Paste a website or Facebook page link" value={links[0]} onChange={(v) => setLink(0, v)} onBlur={checkOnLeave(0)} error={errors[0]} />

      {/* the box that slides open clips what spills out of it, so it is made wider than the form and padded back: the focus ring then has room */}
      <div className="-mx-2">
        <Collapse open={second}>
          <div className="flex flex-col gap-2 p-2">
            {findFb ? (
              <div className="relative flex min-h-12 items-center gap-3 rounded-full bg-white/60 py-2 pl-5 pr-12 text-sm text-muted-foreground ring-1 ring-black/[0.06]">
                <Search className="size-[18px] shrink-0" strokeWidth={1.5} />
                <span>We&apos;ll look for its Facebook page on the website and ask you to confirm which one.</span>
                <button type="button" onClick={closeSecond} aria-label="Remove this link" className="absolute right-3 top-1/2 grid size-7 -translate-y-1/2 place-items-center rounded-full transition-colors hover:bg-black/[0.05] hover:text-foreground">
                  <X className="size-4" strokeWidth={1.75} />
                </button>
              </div>
            ) : (
              <>
                <LinkField index={1} label="Second link" placeholder={firstIsFacebook ? "Add its website (optional)" : "Add its Facebook page (optional)"} value={links[1]} onChange={(v) => setLink(1, v)} onBlur={checkOnLeave(1)} error={errors[1]} onRemove={closeSecond} />
                {!firstIsFacebook && !!links[0].trim() && !links[1].trim() && (
                  <button type="button" onClick={() => setFindFb(true)} className="flex w-fit items-center gap-1.5 px-4 text-sm text-primary transition-opacity hover:opacity-80">
                    <Search className="size-3.5" strokeWidth={1.75} /> No link? Let us find it from the website
                  </button>
                )}
              </>
            )}
          </div>
        </Collapse>
      </div>

      {!second && (
        <button type="button" onClick={() => setSecond(true)} className="flex w-fit items-center gap-1.5 px-4 text-sm text-primary transition-opacity hover:opacity-80">
          <Plus className="size-3.5" strokeWidth={2} />
          {links[0].trim() && !linkProblem(links[0]) ? (firstIsFacebook ? "Add its website too" : "Add its Facebook page too") : "Add a second link"}
          <span className="text-muted-foreground">(optional)</span>
        </button>
      )}

      <Collapse open={entries.length > 0}>
        <CostLine estimate={estimate} state={estimateState} settings={settings} />
      </Collapse>

      {(conflict || formError || submitting) && (
        <p data-banner className={`px-4 text-sm ${submitting ? "text-muted-foreground" : "text-destructive"}`} role={submitting ? "status" : "alert"}>
          {submitting ? "Checking your links…" : (formError ?? conflict)}
        </p>
      )}

      <PillButton type="submit" className="self-center" loading={busy}>
        Analyze brand
      </PillButton>

      {duplicate && (
        <ConfirmDialog
          title="You've analyzed this brand before"
          onClose={() => setDuplicate(null)}
          actions={[
            { label: "Cancel", onClick: () => setDuplicate(null) },
            { label: "Analyze again", onClick: start },
            { label: "Open existing", tone: "primary", autoFocus: true, onClick: () => startOpening(() => router.push(`/analysis/${duplicate.id}`)) },
          ]}
        >
          <p>
            <span className="font-medium text-foreground">{duplicate.title}</span> was analyzed {timeAgo(duplicate.created_at)}. Opening it is free and keeps your edits.
          </p>
          <p>Analyzing again starts a new analysis, and may use Apify credits.</p>
        </ConfirmDialog>
      )}
    </form>
  );
}
