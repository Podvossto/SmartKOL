import type { Analysis } from "./analysis-api";

const host = (url: string | null | undefined) => (url ? url.replace(/^https?:\/\/(www\.)?/, "").split("/")[0] : "");

/** What to call an analysis before (or without) a finished profile. */
export function analysisTitle(a: Analysis): string {
  if (a.profile) return a.profile.brand_name;
  if (a.facebook?.title) return a.facebook.title.split("|")[0].trim();
  if (a.website?.title) return a.website.title.split("|").pop()!.trim();
  return host(a.website_url) || (a.facebook?.url ?? "").split("/").pop() || "New analysis";
}

/** The inputs this analysis was built from, as short labels for the header. */
export function sourceLabels(a: Analysis): { label: string; value: string; platform: "website" | "facebook" }[] {
  const facebook = a.facebook?.url ?? a.selected_facebook ?? a.requested_facebook;
  return [
    ...(a.website_url ? [{ label: "Website", value: host(a.website_url), platform: "website" as const }] : []),
    ...(facebook ? [{ label: "Facebook", value: facebook.split("/").pop() ?? "", platform: "facebook" as const }] : []),
  ];
}
