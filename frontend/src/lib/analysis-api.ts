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

export type Axis = "relevance" | "engagement" | "audience" | "activity";
export type Weights = Record<Axis, number>;

/** Numbers computed from a creator's own latest videos (not lifetime totals). */
export type Metrics = {
  videos: number;
  median_views: number;
  median_er: number | null;
  posts_per_week: number | null;
  last_post: string | null;
  days_since_last_post: number | null;
  ad_share: number;
  shop_share: number;
  read_at: string;
};

/** Four axes 0-100. Relevance and audience come from the AI (audience is an estimate); engagement and activity are computed from the numbers. */
export type Score = Record<Axis, number> & {
  category: number;
  style: number;
  product: number;
  safety: number;
  reason: string;
  audience_reason: string;
  confidence: "low" | "medium" | "high";
  /** The model's guess at who watches this creator; absent on scores made before it was asked. */
  viewers?: { age: string; gender: string; interests: string[] } | null;
  engagement_note: string;
  activity_note: string;
  flags: string[];
  model: string | null;
  scored_at: string;
};

/** What a background job reports. `status` is missing until the job has run once. */
export type JobState = { status?: "running" | "done" | "error"; error?: string | null; usd?: number; model?: string | null; scored?: number; failed?: number; missing?: string[]; cached?: boolean };

export type CreatorsState = {
  status: "idle" | "running" | "done" | "error";
  phase: "searching" | "sorting" | null;
  plan: PlanItem[];
  hashtags: string[];
  videos: number;
  usd: number;
  cached: boolean;
  searched_at: string | null;
  error: string | null;
  classify_error: string | null;
  found: number;
  enrich: JobState;
  scoring: JobState;
  weights: Weights;
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
  creators: CreatorsState;
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

/** One hashtag of a search and how many videos to read from it. */
export type PlanItem = { hashtag: string; videos: number };

export type Creator = {
  username: string;
  nickname: string;
  url: string;
  bio: string;
  followers: number | null;
  likes: number | null;
  total_videos: number | null;
  verified: boolean;
  private: boolean;
  videos_found: number;
  thai_share: number;
  last_post: string | null;
  median_views: number;
  ad_videos: number;
  shop_videos: number;
  hashtags: string[];
  /** Written by the model: what kind of account this is, and whether it is a shop selling what the brand sells. */
  kind: "creator" | "shop" | "media" | "other" | null;
  competitor: boolean;
  kind_reason: string;
  has_avatar: boolean;
  samples: { url: string | null; text: string; views: number; has_cover: boolean }[];
  metrics?: Metrics;
  score?: Score;
  /** Weighted mean of the four axes under the current weights; null until the creator is scored. */
  total?: number | null;
  rank?: number;
};

/** 0 switches a numeric filter off. `thai_min` is a percentage. */
export type CreatorFilters = { thai_min: number; skip_private: boolean; max_age_days: number; min_followers: number; max_followers: number; skip_shops: boolean };

export type CreatorList = {
  total: number;
  kept: Creator[];
  dropped: Record<"thai" | "private" | "recent" | "min_followers" | "max_followers" | "shops", number>;
  weights: Weights;
};

export type EnrichEstimate = {
  estimate: { creators: number; videos_each: number; videos: number; usd: number; list_usd: number; cached: boolean };
  account: Estimate["account"];
};

export type CreatorEstimate = {
  estimate: { plan: PlanItem[]; hashtags: string[]; videos: number; runs: number; usd: number; list_usd: number; cached: boolean };
  account: Estimate["account"];
};

/** `kind`: "avatar", or the number of one of the creator's videos (its cover). Fetched by the server, never by TikTok's link. */
export const creatorPictureUrl = (id: string, username: string, kind: string | number) => `/api/analyses/${id}/creators/${encodeURIComponent(username)}/picture/${kind}`;
export const logoUrl = (id: string) => `/api/analyses/${id}/logo`;
export const mediaUrl = (id: string, key: string) => `/api/analyses/${id}/media/${key}`;

const filterQuery = (f: CreatorFilters) => new URLSearchParams(Object.entries({ ...f, thai_min: f.thai_min / 100 }).map(([k, v]) => [k, String(v)])).toString();

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
  creatorsEstimate: (id: string, plan: PlanItem[]) => call<CreatorEstimate>("POST", `/${id}/creators/estimate`, { plan }),
  searchCreators: (id: string, plan: PlanItem[]) => call<Analysis>("POST", `/${id}/creators/search`, { plan }),
  creators: (id: string, f: CreatorFilters) => call<CreatorList>("GET", `/${id}/creators?${filterQuery(f)}`),
  /** The list as shown (same filters and weights) as a CSV file; the browser downloads it from this link. */
  exportUrl: (id: string, f: CreatorFilters) => `/api/analyses/${id}/creators/export.csv?${filterQuery(f)}`,
  creator: (id: string, username: string) => call<Creator>("GET", `/${id}/creators/${encodeURIComponent(username)}`),
  enrichEstimate: (id: string, usernames: string[], videos: number) => call<EnrichEstimate>("POST", `/${id}/creators/enrich/estimate`, { usernames, videos }),
  enrich: (id: string, usernames: string[], videos: number) => call<Analysis>("POST", `/${id}/creators/enrich`, { usernames, videos }),
  score: (id: string, usernames: string[], redo = false) => call<Analysis>("POST", `/${id}/creators/score`, { usernames, redo }),
  setWeights: (id: string, w: Weights) => call<{ weights: Weights }>("PUT", `/${id}/creators/weights`, w),
  saveProfile: (id: string, profile: Profile) => call<Analysis>("PUT", `/${id}/profile`, profile),
};
