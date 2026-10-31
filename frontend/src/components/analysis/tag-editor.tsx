"use client";

import { Check, X } from "lucide-react";
import { useState } from "react";

import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";

/** A list of removable tags with an add box. Given `isOn` and `onToggle`, each tag is also a switch: in or left out. */
export function TagEditor({
  label,
  hint,
  tags,
  prefix = "",
  onChange,
  isOn,
  onToggle,
  aside,
}: {
  label: string;
  hint: string;
  tags: string[];
  prefix?: string;
  onChange: (tags: string[]) => void;
  isOn?: (tag: string) => boolean;
  onToggle?: (tag: string) => void;
  aside?: React.ReactNode;
}) {
  const [draft, setDraft] = useState("");

  function add() {
    const value = draft.trim().replace(/^#/, "");
    if (value && !tags.some((t) => t.toLowerCase() === value.toLowerCase())) onChange([...tags, value]);
    setDraft("");
  }

  return (
    <div className="flex flex-col gap-2.5">
      <div>
        <div className="flex items-baseline justify-between gap-3">
          <p className="text-sm font-medium">{label}</p>
          {aside && <span className="text-sm text-muted-foreground">{aside}</span>}
        </div>
        <p className="text-xs text-muted-foreground">{hint}</p>
      </div>
      <ul className="flex flex-wrap gap-2">
        {tags.map((tag) => {
          const on = isOn?.(tag) ?? true;
          const remove = (
            <button type="button" aria-label={`Remove ${prefix}${tag}`} className="shrink-0 rounded-full p-0.5 transition-colors hover:bg-primary/15" onClick={() => onChange(tags.filter((t) => t !== tag))}>
              <X className="size-3.5" strokeWidth={1.75} />
            </button>
          );
          if (!onToggle)
            return (
              <li key={tag} className="flex max-w-full items-center gap-1 rounded-full bg-accent py-1 pl-3 pr-1.5 text-sm text-accent-foreground">
                <span className="min-w-0 truncate">
                  {prefix}
                  {tag}
                </span>
                {remove}
              </li>
            );
          return (
            <li
              key={tag}
              className={cn(
                "flex max-w-full items-center rounded-full pr-1.5 text-sm ring-1 transition-colors",
                on ? "bg-primary/10 text-primary ring-primary/30" : "bg-white/60 text-muted-foreground ring-black/15",
              )}
            >
              <button type="button" aria-pressed={on} onClick={() => onToggle(tag)} className="flex min-w-0 items-center gap-1 rounded-full py-1 pl-3 pr-1 focus-visible:outline-2 focus-visible:outline-ring">
                <Check className={cn("size-3.5 shrink-0", !on && "hidden")} strokeWidth={2} />
                <span className="min-w-0 truncate">
                  {prefix}
                  {tag}
                </span>
              </button>
              {remove}
            </li>
          );
        })}
      </ul>
      <Input
        value={draft}
        placeholder="Add and press Enter"
        aria-label={`Add to ${label}`}
        className="h-10"
        onChange={(e) => setDraft(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter") {
            e.preventDefault();
            add();
          }
        }}
        onBlur={add}
      />
    </div>
  );
}
