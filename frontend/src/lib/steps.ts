import type { Analysis } from "./analysis-api";

export type StepKey = "brand" | "profile" | "creators" | "results";

/**
 * The analysis workflow, in one place. To add a step: add a row here and a page under app/analysis/[id]/.
 * `ready` decides whether the step can be opened yet; `href` is where it lives.
 */
export const STEPS: { key: StepKey; label: string; href: (id: string) => string; ready: (a: Analysis) => boolean }[] = [
  { key: "brand", label: "Brand", href: (id) => `/analysis/${id}`, ready: () => true },
  { key: "profile", label: "Profile", href: (id) => `/analysis/${id}`, ready: (a) => a.profile !== null },
  { key: "creators", label: "Creators", href: (id) => `/analysis/${id}/creators`, ready: (a) => a.profile !== null },
  { key: "results", label: "Results", href: (id) => `/analysis/${id}/results`, ready: () => false }, // opens once a creator search exists
];

export function activeStep(pathname: string, analysis: Analysis): StepKey {
  if (pathname.endsWith("/results")) return "results";
  if (pathname.endsWith("/creators")) return "creators";
  return analysis.status === "done" ? "profile" : "brand";
}
