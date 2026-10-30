import { BackLink } from "@/components/back-link";
import { SettingsForm } from "@/components/settings/settings-form";

export default function SettingsPage() {
  return (
    <main className="mx-auto flex w-full max-w-2xl flex-1 flex-col gap-6 px-4 pb-20 pt-6">
      <BackLink href="/" label="Back to home" />
      <div>
        <h1 className="font-heading text-2xl font-semibold tracking-tight">Settings</h1>
        <p className="text-muted-foreground">Connect the data and AI accounts SmartKOL uses. Keys are stored encrypted and never shown again.</p>
      </div>
      <SettingsForm />
    </main>
  );
}
