import { Disclosure } from "@/components/ui/disclosure";

import { Eyebrow } from "./panel";

const STEPS = [
  {
    name: "Find",
    text: "Each hashtag above is searched on TikTok. The creators behind the latest videos are collected and duplicates are merged.",
  },
  {
    name: "Filter",
    text: "Keeps public accounts that post mostly in Thai, were active in the last 30 days and have at least 10K followers. Each filter can be switched off.",
  },
  {
    name: "Read",
    text: "For the best candidates, their recent videos are read, so engagement is measured on real views, not on follower counts.",
  },
  {
    name: "Score",
    text: "Each creator is scored on the four criteria below. The brief's ideal creator (niches, style, avoid list) is what the AI judges them against.",
  },
];

const CRITERIA = [
  {
    name: "Relevance",
    weight: 40,
    text: "Fits the niches and style in the ideal creator, and none of the avoid list. Judged by the AI, with a reason.",
  },
  {
    name: "Engagement",
    weight: 25,
    text: "Likes, comments and shares per view, compared with creators of a similar size.",
  },
  {
    name: "Audience fit",
    weight: 20,
    text: "Whether their viewers are likely the brand's customers. Estimated by the AI: TikTok does not publish audience data.",
  },
  {
    name: "Activity",
    weight: 15,
    text: "Posts regularly, steady views, few paid posts, no sign of bought followers.",
  },
];

/** Plain-language method, folded away until someone wants to read how creators are found and ranked. */
export function SearchMethod() {
  return (
    <Disclosure
      title="How creators are found and scored"
      hint="search steps and the four criteria"
    >
      <div className="grid gap-8 lg:grid-cols-2">
        <section
          aria-label="How the search works"
          className="flex flex-col gap-4"
        >
          <Eyebrow>How the search works</Eyebrow>
          <ol className="flex flex-col gap-3.5">
            {STEPS.map((step, i) => (
              <li key={step.name} className="flex gap-3">
                <span className="grid size-6 shrink-0 place-items-center rounded-full bg-primary/10 text-xs font-medium text-primary">
                  {i + 1}
                </span>
                <p className="text-sm">
                  <span className="font-medium">{step.name}.</span>{" "}
                  <span className="text-muted-foreground">{step.text}</span>
                </p>
              </li>
            ))}
          </ol>
        </section>
        <section
          aria-label="How creators are scored"
          className="flex flex-col gap-4"
        >
          <Eyebrow>How creators are scored</Eyebrow>
          <ul className="flex flex-col gap-3.5">
            {CRITERIA.map((c) => (
              <li key={c.name} className="flex flex-col gap-1">
                <div className="flex items-center justify-between gap-3 text-sm">
                  <span className="font-medium">{c.name}</span>
                  <span className="tabular-nums text-muted-foreground">
                    {c.weight}%
                  </span>
                </div>
                <div className="h-1 overflow-hidden rounded-full bg-muted">
                  <div
                    className="h-full rounded-full bg-primary/70"
                    style={{ width: `${c.weight * 2.5}%` }}
                  />
                </div>
                <p className="text-sm text-muted-foreground">{c.text}</p>
              </li>
            ))}
          </ul>
        </section>
      </div>
    </Disclosure>
  );
}
