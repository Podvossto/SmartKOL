"use client";

import { Check } from "lucide-react";
import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { Disclosure } from "@/components/ui/disclosure";
import { Badge } from "@/components/ui/badge";
import { type PromptView, settingsApi } from "@/lib/settings-api";

import { errorMessage } from "./shared";

const MAX_CHARS = 20_000; // the same limit the server enforces

function PromptCard({ prompt, onChange }: { prompt: PromptView; onChange: (next: PromptView) => void }) {
  const [text, setText] = useState(prompt.text);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);
  const [asking, setAsking] = useState(false);
  const dirty = text.trim() !== prompt.text.trim();
  const differsFromBuiltIn = text.trim() !== prompt.default.trim();

  async function run(action: () => Promise<PromptView>, after?: (next: PromptView) => void) {
    setBusy(true);
    setError(null);
    setSaved(false);
    try {
      const next = await action();
      onChange(next);
      after?.(next);
      setSaved(true);
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  const save = () => run(() => settingsApi.savePrompt(prompt.id, text), (next) => setText(next.text));
  const resetSaved = () =>
    run(() => settingsApi.resetPrompt(prompt.id), (next) => {
      setText(next.text);
      setAsking(false);
    });

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex flex-wrap items-center gap-3">
          {prompt.title} {prompt.edited ? <Badge>Edited by you</Badge> : <Badge variant="secondary">Built-in</Badge>}
        </CardTitle>
        <CardDescription>
          {prompt.description} <span className="text-foreground/70">{prompt.used_when}</span>
        </CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        <div className="flex flex-col gap-2">
          <label htmlFor={`prompt-${prompt.id}`} className="text-sm font-medium">
            Instructions
          </label>
          <textarea
            id={`prompt-${prompt.id}`}
            value={text}
            onChange={(e) => {
              setText(e.target.value);
              setSaved(false);
            }}
            rows={16}
            spellCheck={false}
            aria-invalid={error ? true : undefined}
            className="w-full resize-y rounded-2xl bg-white p-4 font-mono text-[13px] leading-relaxed ring-1 ring-black/10 focus-visible:outline-2 focus-visible:outline-ring aria-invalid:ring-destructive"
          />
          <p className="flex flex-wrap items-center justify-between gap-2 text-xs text-muted-foreground">
            <span>Write in plain sentences, one rule per line is easiest to read. The reply format below is added for you.</span>
            <span className={text.length > MAX_CHARS ? "text-destructive" : undefined}>
              {text.length.toLocaleString()} / {MAX_CHARS.toLocaleString()}
            </span>
          </p>
        </div>

        <Disclosure title="Reply format" hint="fixed, added after your instructions">
          <div className="px-6 pb-5">
            <p className="mb-3 text-sm text-muted-foreground">The app reads the AI&apos;s reply by this shape, so it can&apos;t be changed here. Your instructions can still decide what goes inside it.</p>
            <pre className="max-h-72 overflow-auto whitespace-pre-wrap rounded-2xl bg-muted/60 p-4 font-mono text-xs leading-relaxed">{prompt.output_format}</pre>
          </div>
        </Disclosure>

        <div className="flex flex-wrap items-center gap-3">
          <Button onClick={save} disabled={busy || !dirty || text.length > MAX_CHARS || !text.trim()}>
            Save changes
          </Button>
          <Button variant="outline" onClick={() => (prompt.edited ? setAsking(true) : setText(prompt.default))} disabled={busy || (!prompt.edited && !differsFromBuiltIn)}>
            Reset to default
          </Button>
          {saved && !dirty && (
            <span className="flex items-center gap-1.5 text-sm text-muted-foreground" role="status">
              <span className="grid size-5 place-items-center rounded-full bg-primary text-primary-foreground">
                <Check className="size-3" strokeWidth={3} />
              </span>
              Saved. Used from the next {prompt.id === "brand_brief" ? "analysis" : "search"}.
            </span>
          )}
        </div>
        {error && (
          <p className="text-sm text-destructive" role="alert">
            {error}
          </p>
        )}
      </CardContent>
      {asking && (
        <ConfirmDialog
          title="Go back to the built-in instructions?"
          onClose={() => setAsking(false)}
          actions={[
            { label: "Keep mine", tone: "primary", autoFocus: true, onClick: () => setAsking(false) },
            { label: busy ? "Resetting…" : "Reset to default", tone: "danger", onClick: resetSaved },
          ]}
        >
          <p>Your version of &ldquo;{prompt.title}&rdquo; will be deleted. Results you already have are not changed.</p>
        </ConfirmDialog>
      )}
    </Card>
  );
}

/** The instructions the AI follows, one card each. Only the instructions can be edited; the reply format stays fixed. */
export function PromptsTab() {
  const [prompts, setPrompts] = useState<PromptView[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    settingsApi.prompts().then(setPrompts).catch((err) => setError(errorMessage(err)));
  }, []);

  if (error) return <p className="text-destructive">Could not load the instructions: {error}</p>;
  if (!prompts) return <p className="text-muted-foreground">Loading…</p>;

  return (
    <div className="flex flex-col gap-6">
      <p className="rounded-2xl bg-white/70 px-5 py-4 text-sm text-muted-foreground ring-1 ring-black/[0.05]">
        These are the instructions the AI follows. A change applies to the next analysis or search; results you already have stay as they are. A badly worded instruction can make the AI&apos;s answers worse, and Reset to default always brings the built-in text back.
      </p>
      {prompts.map((p) => (
        <PromptCard key={p.id} prompt={p} onChange={(next) => setPrompts((list) => list && list.map((x) => (x.id === next.id ? next : x)))} />
      ))}
    </div>
  );
}
