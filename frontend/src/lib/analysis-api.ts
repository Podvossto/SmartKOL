import { request } from "./http";

export type StepState = "pending" | "running" | "done" | "skipped" | "error";
export type Step = { key: string; label: string; state: StepState; detail: string | null };

export type Candidate = {
  url: string;
  source: "provided" | "website";
  readable: boolean;
  title: string | null;
  category: string | null;
  followers: number | null;
  address: string | null;
  website: string | null;
  intro: string;
  picture: string | null;
  created: string | null;
  last_post_at: string | null;
  website_match: boolean;
  warnings: string[];
};

export type PostStats = {
  posts_read: number;
  avg_likes?: number;
  avg_comments?: number;
  avg_shares?: number;
  posts_last_30d?: number;
  posts_per_week?: number | null;
  engagement_rate_pct?: number | null;
  top_post?: { text: string; likes: number; comments: number; shares: number; url: string | null };
};

export type FacebookInfo = Candidate & { stats: PostStats };

export type SourceSummary = { summary: string; key_points: string[] };

export type Pillar = { theme: string; detail: string; performance: "strong" | "average" | "weak" | "unknown" };

export type Profile = {
  brand_name: string;
  category: string;
  price_tier: "budget" | "mid" | "premium" | "unknown";
  positioning: string;
  summary: string;
  products: string[];
  audience: { description: string; age_range: string; gender: string; interests: string[]; lifestyle: string; media_habits: string[] };
  voice: { traits: string[]; style: string; dos: string[]; donts: string[] };
  pillars: Pillar[];
  formats: string[];
  creator_fit: { niches: string[]; content_styles: string[]; audience_match: string; language: string; avoid: string[] };
  language: string;
  tiktok: { hashtags_th: string[]; hashtags_en: string[]; keywords: string[] };
  evidence: { fact: string; source: "website" | "facebook" | "both" }[];
  gaps: string[];
  by_source: Partial<Record<"website" | "facebook", SourceSummary>>;
  edited: ("creator_fit" | "tiktok")[];
};

export type Cost = {
  apify_usd: number;
  llm_usd: number;
  llm_known: boolean;
  llm_input_tokens: number;
  llm_output_tokens: number;
  llm_model: string | null;
  cached_runs: number;
};

export type Analysis = {
  id: string;
  mode: "both" | "website" | "facebook";
  discover: boolean;
  eta: [number, number] | null;
  warnings: string[];
  status: "running" | "awaiting_facebook" | "profiling" | "done" | "error";
  website_url: string | null;
  facebook: FacebookInfo | null;
  steps: Step[];
  website: {
    url: string;
    title: string | null;
    description: string | null;
    pages: { url: string; title: string | null; chars: number }[];
    socials: Record<string, string[]>;
  } | null;
  facebook_candidates: Candidate[];
  recommended: string | null;
  selected_facebook: string | null;
  requested_facebook: string | null;
  profile: Profile | null;
  has_logo: boolean;
  media: { key: string; role: "banner" | "sample"; source: "facebook" | "website"; link: string | null; caption: string; video: boolean }[];
  cost: Cost;
  error: string | null;
};

const call = <T>(method: string, path: string, body?: unknown) => request<T>(method, `/api/analyses${path}`, body);

export type RecentItem = {
  id: string;
  title: string;
  mode: Analysis["mode"];
  status: Analysis["status"];
  has_logo: boolean;
  created_at: string;
  website: string | null;
  facebook: string | null;
};

export type Estimate = {
  apify: { low_usd: number; high_usd: number; cached: boolean; note: string } | null;
  account: { remaining_usd: number; limit_usd: number; plan: string | null; cycle_end: string | null } | null;
  llm: { model: string; provider: string } | null;
};

export const logoUrl = (id: string) => `/api/analyses/${id}/logo`;
export const mediaUrl = (id: string, key: string) => `/api/analyses/${id}/media/${key}`;

export const analysisApi = {
  estimate: (website_url: string, facebook_url: string, find_facebook = false) =>
    call<Estimate>("POST", "/estimate", { website_url: website_url || null, facebook_url: facebook_url || null, find_facebook }),
  recent: () => call<RecentItem[]>("GET", ""),
  remove: (id: string) => call<{ deleted: string }>("DELETE", `/${id}`),
  start: (website_url: string, facebook_url: string, find_facebook = false) =>
    call<Analysis>("POST", "", { website_url: website_url || null, facebook_url: facebook_url || null, find_facebook }),
  retry: (id: string) => call<Analysis>("POST", `/${id}/retry`),
  get: (id: string) => call<Analysis>("GET", `/${id}`),
  confirmFacebook: (id: string, facebook_url: string | null) =>
    call<Analysis>("POST", `/${id}/profile`, { facebook_url }),
  saveProfile: (id: string, profile: Profile) => call<Analysis>("PUT", `/${id}/profile`, profile),
};
