import { NewAnalysisForm } from "@/components/analysis/new-analysis-form";
import { Rise } from "@/components/analysis/panel";
import { RecentList } from "@/components/analysis/recent-list";

export default function Home() {
  return (
    <main className="mx-auto flex w-full max-w-2xl flex-1 flex-col gap-14 px-4 pb-20 pt-16 sm:pt-28">
      <div className="flex flex-col gap-8">
        <Rise className="flex flex-col items-center gap-3 text-center">
          <h1 className="font-heading text-4xl font-semibold tracking-tight text-balance sm:text-5xl">Find the right Thai TikTok creators for a brand</h1>
          <p className="text-lg text-muted-foreground">Paste a website or a Facebook page to begin.</p>
        </Rise>
        <Rise index={1}>
          <NewAnalysisForm />
        </Rise>
      </div>
      <Rise index={2}>
        <RecentList />
      </Rise>
    </main>
  );
}
