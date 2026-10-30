"use client";

import { Gauge } from "lucide-react";
import Link from "next/link";
import { useEffect, useRef, useState } from "react";

import { LOGOS, PROVIDER_NAMES } from "@/lib/brand-logos";
import { usd } from "@/lib/format";
import { type ApifyAccount, type LlmBalance, type SettingsView, settingsApi } from "@/lib/settings-api";
import { cn } from "@/lib/utils";

type Loaded = { settings: SettingsView; apify: ApifyAccount | null; llm: LlmBalance | null };

function Heading({ logo, children }: { logo?: string; children: React.ReactNode }) {
  return (
    <h3 className="flex items-center gap-2 text-xs font-medium uppercase tracking-wide text-muted-foreground">
      {logo && (
        // eslint-disable-next-line @next/next/no-img-element
        <img src={logo} alt="" className="size-5 rounded-md bg-white object-contain ring-1 ring-black/[0.06]" />
      )}
      {children}
    </h3>
  );
}

/** What is connected and what is left, one click from any page. Looked up when opened, so it is never stale. */
export function UsageMenu() {
  const [open, setOpen] = useState(false);
  const [data, setData] = useState<Loaded | "failed" | null>(null);
  const box = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    let live = true;
    (async () => {
      try {
        const settings = await settingsApi.get();
        const apify = settings.apify.configured ? await settingsApi.testApify().catch(() => null) : null;
        const llm = settings.llm.configured ? await settingsApi.llmBalance().catch(() => null) : null;
        if (live) setData({ settings, apify, llm });
      } catch {
        if (live) setData("failed");
      }
    })();
    const close = (e: MouseEvent | KeyboardEvent) => {
      if (e instanceof KeyboardEvent ? e.key === "Escape" : !box.current?.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", close);
    document.addEventListener("keydown", close);
    return () => {
      live = false;
      document.removeEventListener("mousedown", close);
      document.removeEventListener("keydown", close);
    };
  }, [open]);

  const loaded = data && data !== "failed" ? data : null;
  const percent = loaded?.apify ? Math.min(100, Math.round((loaded.apify.usage_usd / (loaded.apify.limit_usd || 1)) * 100)) : 0;

  return (
    <div ref={box} className="relative">
      <button
        type="button"
        aria-expanded={open}
        aria-haspopup="dialog"
        onClick={() => {
          setData(null);
          setOpen(!open);
        }}
        className={cn("flex items-center gap-1.5 rounded-full px-3 py-1 text-[13px] transition-colors duration-500", open ? "bg-primary/10 font-medium text-primary" : "text-muted-foreground hover:text-foreground")}
      >
        <Gauge className="size-3.5" strokeWidth={1.75} /> Usage
      </button>
      {open && (
        <div role="dialog" aria-label="Usage and connections" className="animate-rise absolute right-0 top-full z-40 mt-2 flex w-72 max-w-[calc(100vw-2rem)] flex-col gap-4 rounded-2xl bg-white p-4 text-sm shadow-[0_20px_50px_-15px_rgba(20,30,80,0.35)] ring-1 ring-black/[0.06]">
          {data === null && <p className="text-muted-foreground">Checking…</p>}
          {data === "failed" && <p className="text-destructive">Couldn&apos;t reach the server.</p>}
          {loaded && (
            <>
              <section className="flex flex-col gap-1.5">
                <Heading logo={LOGOS.apify}>Apify credits</Heading>
                {!loaded.settings.apify.configured ? (
                  <p className="text-muted-foreground">Not connected.</p>
                ) : loaded.apify ? (
                  <>
                    <p>
                      <span className="font-medium">{usd(loaded.apify.remaining_usd)}</span> left of {usd(loaded.apify.limit_usd)} this month
                    </p>
                    <div className="h-1.5 overflow-hidden rounded-full bg-muted" aria-hidden>
                      <div className="h-full rounded-full bg-primary/70 transition-[width] duration-700" style={{ width: `${percent}%` }} />
                    </div>
                    <p className="text-xs text-muted-foreground">
                      {loaded.apify.plan} plan{loaded.apify.cycle_end ? ` · resets ${new Date(loaded.apify.cycle_end).toLocaleDateString("en", { day: "numeric", month: "short" })}` : ""}
                    </p>
                  </>
                ) : (
                  <p className="text-muted-foreground">Connected, but the balance couldn&apos;t be read.</p>
                )}
              </section>
              <section className="flex flex-col gap-1.5">
                <Heading logo={loaded.settings.llm.provider ? LOGOS[loaded.settings.llm.provider] : undefined}>Language model</Heading>
                {loaded.settings.llm.configured ? (
                  <>
                    <p>
                      <span className="font-medium">{loaded.settings.llm.model}</span>
                      {loaded.settings.llm.provider && <span className="text-muted-foreground"> · {PROVIDER_NAMES[loaded.settings.llm.provider]}</span>}
                    </p>
                    {loaded.llm?.remaining_usd != null ? (
                      <p>
                        <span className="font-medium">{usd(loaded.llm.remaining_usd)}</span> left of {usd(loaded.llm.limit_usd ?? 0)} on this key
                      </p>
                    ) : loaded.llm?.usage_usd != null ? (
                      <p>
                        <span className="font-medium">{usd(loaded.llm.usage_usd)}</span> used on this key, no limit set
                      </p>
                    ) : (
                      <p className="text-xs text-muted-foreground">This provider doesn&apos;t report a balance. Check it with them.</p>
                    )}
                  </>
                ) : (
                  <p className="text-muted-foreground">Not connected.</p>
                )}
              </section>
              <Link href="/settings" onClick={() => setOpen(false)} className="w-fit text-primary underline-offset-4 hover:underline">
                Manage in Settings
              </Link>
            </>
          )}
        </div>
      )}
    </div>
  );
}
