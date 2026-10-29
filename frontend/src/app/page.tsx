import { BackendStatus } from "@/components/backend-status";

export default function Home() {
  return (
    <main className="mx-auto flex w-full max-w-3xl flex-1 flex-col justify-center gap-6 px-4 py-16">
      <h1 className="font-heading text-4xl font-semibold tracking-tight">SmartKOL</h1>
      <p className="text-muted-foreground">
        Match brands with Thai TikTok creators — จับคู่แบรนด์กับครีเอเตอร์ TikTok ไทย
      </p>
      <BackendStatus />
    </main>
  );
}
