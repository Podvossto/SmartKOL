"use client";

import { useEffect, useState } from "react";

import { type Profile, analysisApi } from "@/lib/analysis-api";
import { errorMessage } from "@/lib/errors";

import { useCurrentAnalysis } from "./context";

// One list for the user: the profile keeps Thai and English apart, so they are split again on save.
const toList = (p: Profile["tiktok"]) => [...p.hashtags_th, ...p.hashtags_en];
const isThai = (tag: string) => /[฀-๿]/.test(tag);
const SAVE_DELAY_MS = 700;

/** The hashtags a creator search can use. Every change to the list is saved on its own a moment after you stop typing. */
export function useHashtagList() {
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

  return { tags, setTags, status, error, isSaved: JSON.stringify(tags) === saved, edited: profile.edited.includes("tiktok") };
}
