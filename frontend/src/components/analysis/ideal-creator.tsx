"use client";

import { Pencil } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { type Profile, analysisApi } from "@/lib/analysis-api";
import { errorMessage } from "@/lib/errors";

import { useCurrentAnalysis } from "./context";
import { Eyebrow, FactRow } from "./panel";
import { TagEditor } from "./tag-editor";

const list = (items: string[]) => items.join(" · ");

/** The kind of creator the search and the scoring will look for. The model proposes it; the person can correct it. */
export function IdealCreator() {
  const { analysis, adopt } = useCurrentAnalysis();
  const profile = analysis.profile as Profile;
  const fit = profile.creator_fit;
  const [draft, setDraft] = useState<Profile["creator_fit"] | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const edit = (patch: Partial<Profile["creator_fit"]>) => setDraft((d) => d && { ...d, ...patch });

  async function save() {
    if (!draft) return;
    setBusy(true);
    setError(null);
    try {
      const clean = { ...draft, audience_match: draft.audience_match.trim(), language: draft.language.trim() };
      adopt(await analysisApi.saveProfile(analysis.id, { ...profile, creator_fit: clean }));
      setDraft(null);
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap items-center gap-3">
        <Eyebrow>Ideal creator</Eyebrow>
        {profile.edited.includes("creator_fit") && <span className="text-xs text-muted-foreground">Edited by you</span>}
        {!draft && (
          <button type="button" onClick={() => setDraft(fit)} className="ml-auto flex items-center gap-1.5 text-sm text-primary transition-opacity hover:opacity-80">
            <Pencil className="size-3.5" strokeWidth={1.75} /> Edit
          </button>
        )}
      </div>

      {draft ? (
        <div className="flex flex-col gap-5 rounded-3xl bg-white/80 p-6 ring-1 ring-primary/25">
          <TagEditor label="Niches" hint="The kinds of creator to look for" tags={draft.niches} onChange={(niches) => edit({ niches })} />
          <TagEditor label="Content style" hint="How their videos are made" tags={draft.content_styles} onChange={(content_styles) => edit({ content_styles })} />
          <div className="grid gap-4 sm:grid-cols-2">
            <label className="flex flex-col gap-1.5 text-sm font-medium">
              Their audience
              <Input value={draft.audience_match} onChange={(e) => edit({ audience_match: e.target.value })} placeholder="Who should be watching them" />
            </label>
            <label className="flex flex-col gap-1.5 text-sm font-medium">
              Language
              <Input value={draft.language} onChange={(e) => edit({ language: e.target.value })} placeholder="Thai" />
            </label>
          </div>
          <TagEditor label="Avoid" hint="Creator types or conflicts to leave out" tags={draft.avoid} onChange={(avoid) => edit({ avoid })} />
          <div className="flex flex-wrap items-center gap-3">
            <Button size="sm" onClick={save} disabled={busy || draft.niches.length === 0}>
              {busy ? "Saving…" : "Save"}
            </Button>
            <Button size="sm" variant="ghost" onClick={() => setDraft(null)} disabled={busy}>
              Cancel
            </Button>
            {draft.niches.length === 0 && <span className="text-sm text-muted-foreground">Keep at least one niche.</span>}
            {error && (
              <span className="text-sm text-destructive" role="alert">
                {error}
              </span>
            )}
          </div>
        </div>
      ) : (
        <dl className="divide-y divide-border/70 rounded-3xl bg-white/70 ring-1 ring-black/[0.05]">
          <FactRow label="Niches">{list(fit.niches)}</FactRow>
          {fit.content_styles.length > 0 && <FactRow label="Content style">{list(fit.content_styles)}</FactRow>}
          {fit.audience_match && <FactRow label="Their audience">{fit.audience_match}</FactRow>}
          {fit.language && <FactRow label="Language">{fit.language}</FactRow>}
          {fit.avoid.length > 0 && (
            <FactRow label="Avoid">
              <ul className="flex flex-col gap-1">
                {fit.avoid.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            </FactRow>
          )}
        </dl>
      )}
    </div>
  );
}
