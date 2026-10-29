"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { buttonVariants } from "@/components/ui/button";
import { takeOpenRouterLogin } from "@/lib/pkce";
import { settingsApi } from "@/lib/settings-api";

type State = { kind: "working" } | { kind: "done" } | { kind: "error"; message: string };

async function finishLogin(): Promise<State> {
  const params = new URLSearchParams(window.location.search);
  const code = params.get("code");
  const verifier = takeOpenRouterLogin(params.get("state"));
  if (!code || !verifier) {
    return { kind: "error", message: "This sign-in link is invalid or already used. Start again from Settings." };
  }
  try {
    await settingsApi.exchangeOpenRouter(code, verifier);
    return { kind: "done" };
  } catch (err) {
    return { kind: "error", message: err instanceof Error ? err.message : "Sign-in failed" };
  }
}

export function OpenRouterCallback() {
  const [state, setState] = useState<State>({ kind: "working" });

  useEffect(() => {
    finishLogin().then(setState);
  }, []);

  return (
    <div className="flex flex-col gap-4">
      <h1 className="font-heading text-2xl font-semibold">OpenRouter</h1>
      {state.kind === "working" && <p className="text-muted-foreground">Finishing sign-in…</p>}
      {state.kind === "done" && <p>Connected. Your OpenRouter key was saved securely on the server.</p>}
      {state.kind === "error" && <p className="text-destructive">{state.message}</p>}
      {state.kind !== "working" && (
        <Link href="/settings" className={buttonVariants({ className: "self-start" })}>
          Back to Settings
        </Link>
      )}
    </div>
  );
}
