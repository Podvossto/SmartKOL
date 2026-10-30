"use client";

import { createContext, useContext } from "react";

import type { Analysis } from "@/lib/analysis-api";

type Value = { analysis: Analysis; adopt: (next: Analysis) => void };

export const AnalysisContext = createContext<Value | null>(null);

/** The analysis the current page belongs to. Every step page reads it from here instead of fetching its own. */
export function useCurrentAnalysis(): Value {
  const value = useContext(AnalysisContext);
  if (!value) throw new Error("useCurrentAnalysis must be used inside the analysis layout");
  return value;
}
