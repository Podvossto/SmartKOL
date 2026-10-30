import { ExternalLink } from "lucide-react";

import { type Platform, PlatformIcon } from "@/components/platform-icon";
import type { Analysis } from "@/lib/analysis-api";
import { formatCount, timeAgo } from "@/lib/format";

import { Origin } from "./origin";
import { Eyebrow } from "./panel";

const Block = ({ title, platform, children }: { title: string; platform: Platform; children: React.ReactNode }) => (
  <div className="flex flex-col gap-3">
    <div className="flex items-center gap-2">
      <PlatformIcon platform={platform} />
      <Eyebrow>{title}</Eyebrow>
    </div>
    {children}
  </div>
);

/** What was read, as plain facts first; the model's one-paragraph reading of that source comes after, marked as AI. */
function Reading({ summary, model }: { summary: string; model: string | null }) {
  return (
    <div className="flex flex-col gap-1.5">
      <Origin kind="ai" model={model} className="self-start" />
      <p className="text-[15px]">{summary}</p>
    </div>
  );
}

function WebsiteDetails({ analysis, model }: { analysis: Analysis; model: string | null }) {
  const site = analysis.website;
  const summary = analysis.profile?.by_source.website;
  if (!site) return null;
  return (
    <Block title="From the website" platform="website">
      <div className="flex flex-col gap-1.5">
        <Origin kind="data" className="self-start" />
        <p className="text-sm text-muted-foreground">
          Read {site.pages.length} page{site.pages.length === 1 ? "" : "s"}:{" "}
          {site.pages.map((page, i) => (
            <span key={page.url}>
              {i > 0 && ", "}
              <a href={page.url} target="_blank" rel="noreferrer" className="text-primary underline-offset-4 hover:underline">
                {page.title?.split("|")[0].trim() || new URL(page.url).pathname || "Home"}
              </a>
            </span>
          ))}
        </p>
      </div>
      {summary && <Reading summary={summary.summary} model={model} />}
    </Block>
  );
}

function FacebookDetails({ analysis, model }: { analysis: Analysis; model: string | null }) {
  const page = analysis.facebook;
  const summary = analysis.profile?.by_source.facebook;
  if (!page) return null;
  const s = page.stats;
  const facts = [
    `${formatCount(page.followers)} followers`,
    s.engagement_rate_pct != null && `${s.engagement_rate_pct}% engagement`,
    s.posts_per_week != null && `${s.posts_per_week} posts/week`,
    s.posts_read > 0 && `${formatCount(s.avg_likes)} likes per post`,
    `last post ${timeAgo(page.last_post_at)}`,
  ].filter(Boolean);
  return (
    <Block title="From Facebook" platform="facebook">
      <div className="flex flex-col gap-1.5">
        <Origin kind="data" className="self-start" />
        <p className="text-sm text-muted-foreground">
          <a href={page.url} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 font-medium text-primary underline-offset-4 hover:underline">
            {page.title} <ExternalLink className="size-3" strokeWidth={1.75} />
          </a>
          {" · "}
          {facts.join(" · ")}
        </p>
        {s.top_post && s.top_post.text && (
          <p className="rounded-2xl bg-muted/70 px-4 py-3 text-sm">
            <span className="text-muted-foreground">
              Best recent post · {formatCount(s.top_post.likes)} likes, {formatCount(s.top_post.shares)} shares
            </span>
            <br />
            &ldquo;{s.top_post.text}&rdquo;
          </p>
        )}
      </div>
      {summary && <Reading summary={summary.summary} model={model} />}
    </Block>
  );
}

export function SourceDetails({ analysis }: { analysis: Analysis }) {
  return (
    <>
      <WebsiteDetails analysis={analysis} model={analysis.cost.llm_model} />
      <FacebookDetails analysis={analysis} model={analysis.cost.llm_model} />
    </>
  );
}
