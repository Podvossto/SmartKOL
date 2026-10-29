"use client";

import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";

type Status = "checking" | "ok" | "down";

async function fetchHealth(): Promise<Status> {
  try {
    const res = await fetch("/api/health", { cache: "no-store" });
    return res.ok ? "ok" : "down";
  } catch {
    return "down";
  }
}

export function BackendStatus() {
  const [status, setStatus] = useState<Status>("checking");

  function check() {
    setStatus("checking");
    fetchHealth().then(setStatus);
  }

  useEffect(() => {
    fetchHealth().then(setStatus);
  }, []);

  return (
    <div className="flex items-center gap-3">
      <span data-status={status} className="text-sm">
        Backend: {status === "checking" ? "checking…" : status === "ok" ? "connected" : "unreachable"}
      </span>
      <Button size="sm" onClick={check}>
        Re-check
      </Button>
    </div>
  );
}
