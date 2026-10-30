"use client";

import { X } from "lucide-react";
import { useState } from "react";

import { Input } from "@/components/ui/input";

export function TagEditor({ label, hint, tags, prefix = "", onChange }: { label: string; hint: string; tags: string[]; prefix?: string; onChange: (tags: string[]) => void }) {
  const [draft, setDraft] = useState("");

  function add() {
    const value = draft.trim().replace(/^#/, "");
    if (value && !tags.some((t) => t.toLowerCase() === value.toLowerCase())) onChange([...tags, value]);
    setDraft("");
  }

  return (
    <div className="flex flex-col gap-2.5">
      <div>
        <p className="text-sm font-medium">{label}</p>
        <p className="text-xs text-muted-foreground">{hint}</p>
      </div>
      <ul className="flex flex-wrap gap-2">
        {tags.map((tag) => (
          <li key={tag} className="flex items-center gap-1 rounded-full bg-accent py-1 pl-3 pr-1.5 text-sm text-accent-foreground">
            {prefix}
            {tag}
            <button type="button" aria-label={`Remove ${tag}`} className="rounded-full p-0.5 transition-colors hover:bg-primary/15" onClick={() => onChange(tags.filter((t) => t !== tag))}>
              <X className="size-3.5" strokeWidth={1.75} />
            </button>
          </li>
        ))}
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
