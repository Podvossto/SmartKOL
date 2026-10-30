"use client";

import { useEffect, useState } from "react";

import { type Analysis, analysisApi } from "@/lib/analysis-api";
import { errorMessage } from "@/lib/errors";

const POLL_MS = 1500;

/** Loads an analysis and keeps polling while the server is still working on it. */
export function useAnalysis(id: string) {
  const [analysis, setAnalysis] = useState<Analysis | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [restarts, setRestarts] = useState(0);

  useEffect(() => {
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout> | undefined;

    async function poll() {
      try {
        const next = await analysisApi.get(id);
        if (cancelled) return;
        setAnalysis(next);
        if (next.status === "running" || next.status === "profiling") timer = setTimeout(poll, POLL_MS);
      } catch (err) {
        if (!cancelled) setError(errorMessage(err));
      }
    }

    poll();
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [id, restarts]);

  return {
    analysis,
    error,
    /** Use a fresh server state (e.g. a POST response) and resume polling if needed. */
    adopt: (next: Analysis) => {
      setAnalysis(next);
      setRestarts((n) => n + 1);
    },
  };
}
