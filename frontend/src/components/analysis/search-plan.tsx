"use client";

import { useEffect, useState } from "react";

import { PlatformIcon } from "@/components/platform-icon";
import { Card } from "@/components/ui/card";
import { type Profile, analysisApi } from "@/lib/analysis-api";
import { errorMessage } from "@/lib/errors";

import { useCurrentAnalysis } from "./context";
import { Origin } from "./origin";
import { Eyebrow } from "./panel";
import { TagEditor } from "./tag-editor";

// One list for the user: the profile keeps Thai and English apart, so they are split again on save.
const toList = (p: Profile["tiktok"]) => [...p.hashtags_th, ...p.hashtags_en];
const isThai = (tag: string) => /[฀-๿]/.test(tag);
const SAVE_DELAY_MS = 700;

/** The hashtags a creator search will use. Every change is saved on its own a moment after you stop typing. */
export function SearchPlan() {
  const { analysis, adopt } = useCurrentAnalysis();
  const profile = analysis.profile as Profile;
  const [tags, setTags] = useState(toList(profile.tiktok));
  const [status, setStatus] = useState<"idle" | "saving" | "saved" | "error">("idle");
  const [error, setError] = useState<string | null>(null);
  const saved = JSON.stringify(toList(profile.tiktok));

  useEffect(() => {
    if (JSON.stringify(tags) === saved) return;
    const timer = setTimeout(async () => {
      setStatus("saving");
      setError(null);
      try {
        adopt(await analysisApi.saveProfile(analysis.id, { ...profile, tiktok: { ...profile.tiktok, hashtags_th: tags.filter(isThai), hashtags_en: tags.filter((t) => !isThai(t)) } }));
        setStatus("saved");
      } catch (err) {
        setError(errorMessage(err));
        setStatus("error");
      }
    }, SAVE_DELAY_MS);
    return () => clearTimeout(timer);
  }, [tags, saved, profile, adopt, analysis.id]);

  return (
    <Card>
      <section className="flex flex-col gap-5 px-(--card-spacing)">
        <div className="flex flex-wrap items-center gap-2">
          <PlatformIcon platform="tiktok" />
          <Eyebrow>Hashtags to search on TikTok</Eyebrow>
          <Origin kind="ai" model={analysis.cost.llm_model} />
          {profile.edited.includes("tiktok") && <span className="text-xs text-muted-foreground">Edited by you</span>}
          <span className="ml-auto text-xs text-muted-foreground" role="status" aria-live="polite">
            {status === "saving" && "Saving…"}
            {status === "saved" && JSON.stringify(tags) === saved && "Saved"}
          </span>
        </div>
        <TagEditor label="Hashtags" hint="Suggested from the brand profile. Remove any that don't fit, or add your own. Changes are saved automatically." prefix="#" tags={tags} onChange={setTags} />
        {tags.length === 0 && <p className="text-sm text-muted-foreground">Add at least one hashtag to search.</p>}
        {status === "error" && (
          <p className="text-sm text-destructive" role="alert">
            Couldn&apos;t save: {error}. Your last change will be tried again when you edit the list.
          </p>
        )}
      </section>
    </Card>
  );
}
