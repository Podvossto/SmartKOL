import Link from "next/link";

import { SettingsForm } from "@/components/settings/settings-form";

export default function SettingsPage() {
  return (
    <main className="mx-auto flex w-full max-w-3xl flex-1 flex-col gap-6 px-4 py-12">
      <div>
        <Link href="/" className="text-sm text-muted-foreground hover:text-foreground">
          ← SmartKOL
        </Link>
        <h1 className="mt-2 font-heading text-3xl font-semibold tracking-tight">Settings</h1>
        <p className="text-muted-foreground">
          Connect your own accounts. Keys are stored encrypted on the server and are never shown again.
        </p>
      </div>
      <SettingsForm />
    </main>
  );
}
