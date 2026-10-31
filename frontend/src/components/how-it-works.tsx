"use client";

import { ChevronLeft, ChevronRight, CircleHelp, Cpu, Sparkles, X } from "lucide-react";
import { Fragment, useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";

import { PlatformIcon } from "@/components/platform-icon";
import { LOGOS } from "@/lib/brand-logos";
import { cn } from "@/lib/utils";

import { PHASES, STEPS, type Step, type Tag } from "./how-it-works-steps";

const TAGS: Record<Tag, { name: string; chip: string }> = {
  apify: { name: "Apify", chip: "bg-amber-100 text-amber-900" },
  ai: { name: "AI model", chip: "bg-violet-100 text-violet-900" },
  app: { name: "In the app", chip: "bg-emerald-100 text-emerald-900" },
};
const TAG_ORDER: Tag[] = ["apify", "ai", "app"];
const FIRST = PHASES.map((_, p) => PHASES.slice(0, p).reduce((sum, ph) => sum + ph.steps.length, 0)); // number of the first step of each phase

const tagsOf = (step: Step) => TAG_ORDER.filter((t) => step.tags.includes(t));

function Mark({ tag }: { tag: Tag }) {
  // The chip's text names the service, so the mark itself is decorative.
  // eslint-disable-next-line @next/next/no-img-element
  if (tag === "apify") return <img src={LOGOS.apify} alt="" className="size-3.5 shrink-0 rounded-sm" />;
  const Icon = tag === "ai" ? Sparkles : Cpu;
  return <Icon className="size-3 shrink-0" strokeWidth={2} aria-hidden />;
}

function TagChip({ tag }: { tag: Tag }) {
  return (
    <span className={cn("inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px] font-medium whitespace-nowrap", TAGS[tag].chip)}>
      <Mark tag={tag} />
      {TAGS[tag].name}
    </span>
  );
}

function Platforms({ step }: { step: Step }) {
  if (!step.platforms) return null;
  return (
    <span className="flex shrink-0 items-center gap-1">
      {step.platforms.map((p) => (
        <PlatformIcon key={p} platform={p} className="size-3.5" />
      ))}
    </span>
  );
}

/** A dotted line with a diamond at each end: down inside a phase and on a phone, across between phases on a wide screen. */
function Link({ across = false }: { across?: boolean }) {
  return (
    <div aria-hidden className="flex items-center justify-center">
      <span className={cn("flex flex-col items-center", across && "lg:hidden")}>
        <span className="size-1.5 rotate-45 bg-primary/70" />
        <span className="h-3 border-l-2 border-dotted border-primary/40" />
        <span className="size-1.5 rotate-45 bg-primary/70" />
      </span>
      {across && (
        <span className="hidden w-full items-center px-1 lg:flex">
          <span className="size-2 shrink-0 rotate-45 bg-primary" />
          <span className="flex-1 border-t-2 border-dotted border-primary/50" />
          <span className="size-2 shrink-0 rotate-45 bg-primary" />
        </span>
      )}
    </div>
  );
}

/** What the three tags mean. Plain text: the tags on each step say the rest. A phone gets the chips and one short line. */
function Legend() {
  const note = "hidden sm:inline";
  return (
    <div className="flex flex-col gap-1">
      <ul className="flex flex-wrap gap-x-4 gap-y-1.5 text-xs text-muted-foreground">
        <li className="flex items-center gap-1.5">
          <TagChip tag="apify" /> <span className={note}>billed by Apify</span>
        </li>
        <li className="flex items-center gap-1.5">
          <TagChip tag="ai" />
          <span className={cn(note, "sm:flex sm:items-center sm:gap-1")}>
            billed by your model provider, e.g.
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src={LOGOS.openrouter} alt="" className="size-3.5 rounded-sm" />
            OpenRouter
          </span>
        </li>
        <li className="flex items-center gap-1.5">
          <TagChip tag="app" /> <span className={note}>free, computed locally</span>
        </li>
      </ul>
      <p className="text-xs text-muted-foreground sm:hidden">Apify and the AI model bill your own accounts; the app is free.</p>
    </div>
  );
}

function Node({ step, index, active, onSelect, nodeRef }: { step: Step; index: number; active: boolean; onSelect: () => void; nodeRef: (el: HTMLButtonElement | null) => void }) {
  const Icon = step.icon;
  return (
    <button
      ref={nodeRef}
      type="button"
      onClick={onSelect}
      onFocus={onSelect}
      aria-current={active ? "step" : undefined}
      aria-label={`Step ${index + 1}: ${step.title}. ${tagsOf(step).map((t) => TAGS[t].name).join(", ")}`}
      className={cn(
        "flex w-full items-center gap-3 rounded-2xl bg-white p-2.5 text-left outline-none transition-[box-shadow,transform] duration-300 focus-visible:ring-3 focus-visible:ring-ring/50 motion-reduce:transition-none",
        active ? "shadow-md ring-2 ring-primary" : "ring-1 ring-black/[0.06] hover:-translate-y-0.5 hover:ring-primary/40 motion-reduce:hover:translate-y-0",
      )}
    >
      <span className={cn("grid size-9 shrink-0 place-items-center rounded-xl transition-colors duration-300", active ? "bg-primary text-primary-foreground" : "bg-primary/[0.08] text-primary")}>
        <Icon className="size-[18px]" strokeWidth={1.75} aria-hidden />
      </span>
      <span className="flex min-w-0 flex-1 flex-col gap-1">
        <span className="flex items-center gap-1.5">
          <span className="font-heading text-[15px] font-semibold leading-tight">{step.title}</span>
          <Platforms step={step} />
        </span>
        <span className="flex flex-wrap gap-1">
          {tagsOf(step).map((t) => (
            <TagChip key={t} tag={t} />
          ))}
        </span>
      </span>
    </button>
  );
}

/** One step for a first-time reader: what happens, who does it, what it costs. */
function Detail({ step, index }: { step: Step; index: number }) {
  return (
    <div key={index} className="animate-fade flex flex-col gap-3">
      <div className="flex items-center gap-2">
        <p className="font-heading text-base font-semibold">
          <span className="font-normal text-muted-foreground tabular-nums">{index + 1}. </span>
          {step.title}
        </p>
        <Platforms step={step} />
      </div>
      <p className="text-sm">{step.text}</p>
      <ul className="flex flex-col gap-1.5 text-sm">
        {tagsOf(step).map((t) => (
          <li key={t} className="flex flex-col items-start gap-1 sm:flex-row sm:items-baseline sm:gap-2">
            <TagChip tag={t} />
            <span>{step.roles[t]}</span>
          </li>
        ))}
      </ul>
      <p className="text-sm">
        <span className="font-medium">Price: </span>
        <span className="text-muted-foreground">{step.price}</span>
      </p>
    </div>
  );
}

const control = "flex h-9 shrink-0 items-center gap-1.5 whitespace-nowrap rounded-full px-2.5 text-sm outline-none transition-colors hover:bg-black/[0.05] focus-visible:ring-3 focus-visible:ring-ring/50 disabled:pointer-events-none disabled:opacity-40 sm:px-3.5";

function Popup({ onClose }: { onClose: () => void }) {
  const close = useRef<HTMLButtonElement>(null);
  const nodes = useRef<(HTMLButtonElement | null)[]>([]);
  const [active, setActive] = useState(0);
  const last = STEPS.length - 1;
  const pick = (i: number) => setActive(Math.min(Math.max(i, 0), last));

  useEffect(() => {
    close.current?.focus();
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  // On a phone the diagram scrolls in its own box: keep the chosen step in it.
  useEffect(() => {
    nodes.current[active]?.scrollIntoView({ block: "nearest" });
  }, [active]);

  function onArrows(e: React.KeyboardEvent) {
    const to = { ArrowRight: active + 1, ArrowDown: active + 1, ArrowLeft: active - 1, ArrowUp: active - 1, Home: 0, End: last }[e.key];
    if (to === undefined) return;
    e.preventDefault();
    nodes.current[Math.min(Math.max(to, 0), last)]?.focus(); // focusing a step selects it
  }

  // In the page body, not the header: a header with a blur or a transform would trap a fixed element inside it.
  // The dialog has a fixed size, so moving between steps never makes it jump: the diagram and the detail scroll inside.
  return createPortal(
    <div className="fixed inset-0 z-50 grid place-items-center p-2 sm:p-4">
      <div className="animate-fade fixed inset-0 bg-slate-900/30 backdrop-blur-[2px]" onClick={onClose} aria-hidden />
      <div role="dialog" aria-modal="true" aria-labelledby="how-it-works-title" className="animate-rise relative flex h-[calc(100dvh-1rem)] w-full max-w-6xl flex-col overflow-hidden rounded-3xl bg-white shadow-[0_30px_80px_-20px_rgba(20,30,80,0.45)] ring-1 ring-black/[0.06] sm:h-[min(44rem,calc(100dvh-2rem))]">
        <div className="flex shrink-0 items-start justify-between gap-4 px-4 pt-4 pb-3 sm:px-7 sm:pt-6">
          <div className="flex min-w-0 flex-col gap-2">
            <div>
              <h2 id="how-it-works-title" className="font-heading text-xl font-semibold tracking-tight sm:text-2xl">
                How it works
              </h2>
              <p className="text-sm text-muted-foreground">From a brand to ranked Thai TikTok creators, in {STEPS.length} steps.</p>
            </div>
            <Legend />
          </div>
          <button ref={close} type="button" onClick={onClose} aria-label="Close" className="grid size-9 shrink-0 place-items-center rounded-full text-muted-foreground outline-none transition-colors hover:bg-black/[0.05] hover:text-foreground focus-visible:ring-3 focus-visible:ring-ring/50">
            <X className="size-4" />
          </button>
        </div>

        <div className="flex min-h-0 flex-1 flex-col gap-3 px-3 sm:px-7">
          <div className="min-h-0 flex-1 overflow-y-auto rounded-3xl bg-slate-100/80 p-2.5 sm:p-4 lg:flex-none lg:overflow-visible">
            <div role="group" aria-label="Steps. Use the arrow keys to move between them." onKeyDown={onArrows} className="grid grid-cols-1 lg:grid-cols-[minmax(0,1fr)_2.5rem_minmax(0,1fr)_2.5rem_minmax(0,1fr)]">
              {PHASES.map((phase, p) => (
                <Fragment key={phase.title}>
                  {p > 0 && <Link across />}
                  <section aria-label={phase.title} className="flex flex-col rounded-2xl bg-white/60 p-2.5 ring-1 ring-black/[0.04]">
                    <p className="mb-2 px-1 text-xs font-medium uppercase tracking-wide text-muted-foreground">{phase.title}</p>
                    {phase.steps.map((step, s) => {
                      const i = FIRST[p] + s;
                      return (
                        <Fragment key={step.title}>
                          {s > 0 && <Link />}
                          <Node step={step} index={i} active={i === active} onSelect={() => i !== active && pick(i)} nodeRef={(el) => void (nodes.current[i] = el)} />
                        </Fragment>
                      );
                    })}
                  </section>
                </Fragment>
              ))}
            </div>
          </div>

          {/* Its height comes from the dialog, not from the step shown; a long step scrolls inside. */}
          <div className="h-52 shrink-0 overflow-y-auto rounded-2xl p-1 lg:h-auto lg:min-h-0 lg:flex-1 lg:px-2" aria-live="polite">
            <Detail step={STEPS[active]} index={active} />
          </div>
        </div>

        <div className="flex shrink-0 items-center justify-end gap-2 border-t sm:justify-between border-black/[0.06] px-4 py-2.5 sm:px-7">
          <p className="hidden min-w-0 truncate text-xs text-muted-foreground sm:block">Paid steps use your own accounts, set in Settings.</p>
          <div className="flex items-center gap-1">
            <button type="button" onClick={() => pick(active - 1)} disabled={active === 0} aria-label="Previous step" className={control}>
              <ChevronLeft className="size-4" aria-hidden />
              <span className="hidden sm:inline">Previous</span>
            </button>
            <span className="min-w-10 text-center text-sm tabular-nums text-muted-foreground" aria-hidden>
              {active + 1} / {STEPS.length}
            </span>
            <button type="button" onClick={() => pick(active + 1)} disabled={active === last} aria-label="Next step" className={control}>
              <span className="hidden sm:inline">Next</span>
              <ChevronRight className="size-4" aria-hidden />
            </button>
          </div>
        </div>
      </div>
    </div>,
    document.body,
  );
}

/** The header button that opens the flow as a picture. */
export function HowItWorksButton({ className }: { className?: string }) {
  const [open, setOpen] = useState(false);
  return (
    <>
      <button type="button" onClick={() => setOpen(true)} aria-haspopup="dialog" className={cn("flex items-center gap-1.5 rounded-full px-2 py-1 text-[13px] sm:px-3 text-muted-foreground transition-colors duration-500 hover:text-foreground", className)}>
        <CircleHelp className="size-4" strokeWidth={1.75} />
        <span className="hidden sm:inline">How it works</span>
        <span className="sr-only sm:hidden">How it works</span>
      </button>
      {open && <Popup onClose={() => setOpen(false)} />}
    </>
  );
}
