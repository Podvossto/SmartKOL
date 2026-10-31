import { CirclePlay, Download, FileText, Funnel, Gauge, Globe, ListOrdered, Search, SlidersHorizontal, type LucideIcon } from "lucide-react";

import { AXIS_LABELS, DEFAULT_WEIGHTS } from "@/components/analysis/weights-bar";
import type { Platform } from "@/components/platform-icon";
import type { Axis } from "@/lib/analysis-api";

/** Who does the work in a step, and so who bills for it. */
export type Tag = "apify" | "ai" | "app";

// Apify price lists, the same figures the server estimates with (backend/app/discovery.py and apify_runner.py).
const TIKTOK_VIDEO_USD = 0.0037; // clockworks/tiktok-scraper, per video read
const TIKTOK_RUN_USD = 0.001; // its start fee, per run
const FB_PAGE_USD = 0.012;
const FB_POST_USD = 0.005;
const FB_POSTS_RUN_USD = 0.001;
const FB_POSTS = 10; // latest posts read per Facebook page (backend/app/analyses.py)
const CACHE_DAYS = 7; // a repeat Apify run within this many days comes from the saved copy, at $0

/** Exact, unlike the app's usd(), which rounds $0.0037 to $0.004. */
const usd = (n: number) => `$${Number(n.toFixed(4))}`;

const facebookRead = FB_PAGE_USD + FB_POSTS_RUN_USD + FB_POSTS * FB_POST_USD;
const exampleRead = 10 * 5 * TIKTOK_VIDEO_USD + TIKTOK_RUN_USD; // the Rank panel's default: top 10 creators, 5 videos each
const weights = (Object.keys(AXIS_LABELS) as Axis[]).map((a) => `${AXIS_LABELS[a].name} ${DEFAULT_WEIGHTS[a]}%`).join(", ");

export type Step = {
  title: string;
  icon: LucideIcon;
  platforms?: Platform[]; // where the data comes from, shown as small marks
  tags: Tag[];
  text: string; // one sentence: what happens
  roles: Partial<Record<Tag, string>>; // one line per provider
  price: string; // one line
};

export type Phase = { title: string; steps: Step[] };

export const PHASES: Phase[] = [
  {
    title: "Understand the brand",
    steps: [
      {
        title: "Read the brand",
        icon: Globe,
        platforms: ["website", "facebook"],
        tags: ["apify", "app"],
        text: "Reads what the brand says about itself on its website and Facebook page.",
        roles: {
          apify: `Reads the Facebook page and its ${FB_POSTS} latest posts.`,
          app: "Checks the links, then reads up to 5 website pages in a headless browser.",
        },
        price: `Website free; Facebook page + ${FB_POSTS} posts ≈ ${usd(facebookRead)} (${usd(FB_PAGE_USD)} page, ${usd(FB_POST_USD)} a post, ${usd(FB_POSTS_RUN_USD)} a run).`,
      },
      {
        title: "Write the brief",
        icon: FileText,
        tags: ["ai"],
        text: "Turns what was read into a brand brief: audience, voice, the ideal creator and TikTok hashtags.",
        roles: {
          ai: "One call with the “Brand brief” instructions, editable in Settings.",
        },
        price: "Billed by your model provider; the cost shows in the analysis header.",
      },
      {
        title: "Build the search",
        icon: SlidersHorizontal,
        platforms: ["tiktok"],
        tags: ["app"],
        text: "You edit the hashtags and choose how many videos to read under each.",
        roles: {
          app: "Up to 100 videos a hashtag, 500 in all; works out the price before anything runs.",
        },
        price: "Free.",
      },
    ],
  },
  {
    title: "Find creators",
    steps: [
      {
        title: "Search TikTok",
        icon: Search,
        platforms: ["tiktok"],
        tags: ["apify", "ai", "app"],
        text: "Finds the creators behind the newest videos under each hashtag.",
        roles: {
          apify: "Reads the videos with clockworks/tiktok-scraper.",
          ai: "Labels each account as a creator, shop or media page, 25 per call.",
          app: "Makes one record per creator and hides phone numbers and e-mails.",
        },
        price: `${usd(TIKTOK_VIDEO_USD)} a video + ${usd(TIKTOK_RUN_USD)} a run; the same search within ${CACHE_DAYS} days is free.`,
      },
      {
        title: "Filter",
        icon: Funnel,
        tags: ["app"],
        text: "Narrows the list using the records already saved.",
        roles: {
          app: "Thai captions, creators only, public, account size; each switch shows what it removes.",
        },
        price: "Free.",
      },
      {
        title: "Read latest videos",
        icon: CirclePlay,
        platforms: ["tiktok"],
        tags: ["apify", "app"],
        text: "Reads the latest videos of your top creators, so the numbers reflect what they post now.",
        roles: {
          apify: "Reads 5, 10 or 20 latest videos per creator, pinned ones skipped.",
          app: "Works out median views, engagement rate, posts per week and share of ads.",
        },
        price: `creators × videos × ${usd(TIKTOK_VIDEO_USD)} + ${usd(TIKTOK_RUN_USD)} (10 × 5 = ${usd(exampleRead)}); free again within ${CACHE_DAYS} days.`,
      },
    ],
  },
  {
    title: "Rank and take away",
    steps: [
      {
        title: "Score",
        icon: Gauge,
        tags: ["ai", "app"],
        text: "Each creator gets four scores out of 100, with a reason.",
        roles: {
          ai: "Judges brand fit and estimates audience fit, 10 creators per call.",
          app: "Computes engagement and activity from the videos read.",
        },
        price: "Billed by your model provider; a creator already judged is not asked about again.",
      },
      {
        title: "Rank",
        icon: ListOrdered,
        tags: ["app"],
        text: "A weighted total puts the creators in order; change a weight and the list re-ranks at once.",
        roles: {
          app: `Suggested weights: ${weights}.`,
        },
        price: "Free.",
      },
      {
        title: "Export",
        icon: Download,
        tags: ["app"],
        text: "Downloads the list as you see it, as a CSV for Excel or Sheets.",
        roles: {
          app: "Ranked creators first, Thai names intact; bios and picture links left out.",
        },
        price: "Free.",
      },
    ],
  },
];

export const STEPS: Step[] = PHASES.flatMap((p) => p.steps);
