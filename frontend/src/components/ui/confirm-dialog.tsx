"use client";

import { useEffect, useRef } from "react";

import { cn } from "@/lib/utils";

export type DialogAction = { label: string; onClick: () => void; tone?: "primary" | "danger" | "plain"; autoFocus?: boolean };

const TONES = {
  primary: "bg-primary text-primary-foreground hover:bg-primary/90",
  danger: "bg-destructive/10 text-destructive hover:bg-destructive/20",
  plain: "text-muted-foreground hover:bg-black/[0.05] hover:text-foreground",
} as const;

/** A small modal for a decision the user must make. Escape and a click outside both just close it. */
export function ConfirmDialog({ title, children, actions, onClose }: { title: string; children: React.ReactNode; actions: DialogAction[]; onClose: () => void }) {
  const focus = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    focus.current?.focus();
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  return (
    <div className="fixed inset-0 z-50 grid place-items-center p-4">
      <div className="animate-fade absolute inset-0 bg-slate-900/30 backdrop-blur-[2px]" onClick={onClose} aria-hidden />
      <div role="alertdialog" aria-modal="true" aria-label={title} className="animate-rise relative flex w-full max-w-md flex-col gap-4 rounded-3xl bg-white p-6 shadow-[0_30px_80px_-20px_rgba(20,30,80,0.45)] ring-1 ring-black/[0.06]">
        <h2 className="font-heading text-lg font-semibold tracking-tight">{title}</h2>
        <div className="flex flex-col gap-2 text-[15px] text-muted-foreground">{children}</div>
        <div className="flex flex-wrap justify-end gap-2 pt-1">
          {actions.map((a) => (
            <button
              key={a.label}
              ref={a.autoFocus ? focus : undefined}
              type="button"
              onClick={a.onClick}
              className={cn("rounded-full px-4 py-2 text-sm font-medium outline-none transition-all duration-300 ease-[cubic-bezier(0.32,0.72,0,1)] hover:-translate-y-0.5 focus-visible:ring-3 focus-visible:ring-ring/50 active:translate-y-0", TONES[a.tone ?? "plain"])}
            >
              {a.label}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
