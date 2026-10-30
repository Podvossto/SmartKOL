"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { Button, buttonVariants } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { analysisApi } from "@/lib/analysis-api";
import { errorMessage } from "@/lib/errors";

import { useCurrentAnalysis } from "./context";
import { FacebookPicker } from "./facebook-picker";
import { ProfileOverview } from "./profile-overview";
import { ProgressSteps } from "./progress-steps";

function Failed({ message, onRetry }: { message: string | null; onRetry: () => Promise<void> }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  async function retry() {
    setBusy(true);
    setError(null);
    try {
      await onRetry();
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }
  return (
    <Card className="animate-rise [--card-spacing:--spacing(7)]">
      <div className="flex flex-col gap-4 px-(--card-spacing)">
        <h2 className="font-heading text-xl font-semibold tracking-tight">That didn&apos;t work</h2>
        <p className="text-[15px]" role="alert">
          {message}
        </p>
        {error && <p className="text-sm text-destructive">{error}</p>}
        <div className="flex flex-wrap gap-3">
          <Button onClick={retry} disabled={busy}>
            {busy ? "Retrying…" : "Try again"}
          </Button>
          <Link href="/" className={buttonVariants({ variant: "outline" })}>
            Start over
          </Link>
          <Link href="/settings" className={buttonVariants({ variant: "ghost" })}>
            Check settings
          </Link>
        </div>
      </div>
    </Card>
  );
}

/** The progress card with a way out. Stopping deletes the analysis; what Apify already started is still billed. */
function Running({ title, eta }: { title: string; eta?: [number, number] | null }) {
  const router = useRouter();
  const { analysis } = useCurrentAnalysis();
  const [asking, setAsking] = useState(false);
  const [stopping, setStopping] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function stop() {
    setStopping(true);
    try {
      await analysisApi.remove(analysis.id);
      router.push("/");
    } catch (err) {
      setError(errorMessage(err));
      setStopping(false);
    }
  }

  return (
    <>
      <ProgressSteps title={title} steps={analysis.steps} eta={eta} onCancel={() => setAsking(true)} />
      {asking && (
        <ConfirmDialog
          title="Stop this analysis?"
          onClose={() => setAsking(false)}
          actions={[
            { label: "Keep analyzing", tone: "primary", autoFocus: true, onClick: () => setAsking(false) },
            { label: stopping ? "Stopping…" : "Stop and delete", tone: "danger", onClick: stop },
          ]}
        >
          <p>The analysis will be deleted and you will go back to the start.</p>
          <p>Apify may still charge for what it already started reading, even after you stop. Those credits can&apos;t be refunded.</p>
          {error && <p className="text-destructive">{error}</p>}
        </ConfirmDialog>
      )}
    </>
  );
}

/** Steps 1-2: reading the brand, confirming its Facebook page, reviewing the profile. */
export function BrandStep() {
  const { analysis, adopt } = useCurrentAnalysis();
  switch (analysis.status) {
    case "running":
      return <Running title="Reading the brand" eta={analysis.eta} />;
    case "profiling":
      return <Running title="Writing the profile" />;
    case "awaiting_facebook":
      return <FacebookPicker analysis={analysis} onAdopt={adopt} />;
    case "error":
      return <Failed message={analysis.error} onRetry={async () => adopt(await analysisApi.retry(analysis.id))} />;
    case "done":
      return analysis.profile ? <ProfileOverview /> : null;
  }
}
