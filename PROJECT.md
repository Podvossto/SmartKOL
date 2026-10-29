# SmartKOL — PROJECT.md

AI tool that reads a brand's website and Facebook page, then finds, scores and ranks Thai TikTok creators (KOLs) that fit the brand.
Built for an influencer-marketing team that today shortlists KOLs by hand.

## Scope
### IN — what this project does
- Analyze a brand from its website + Facebook page → structured Brand Profile (category, products, audience, tone, content style, keywords, hashtags)
- Discover Thai TikTok creators from brand-relevant hashtags/keywords
- Enrich a shortlist with recent-video metrics and score each creator on relevance, engagement, audience fit and activity
- Show a ranked, explained list with TikTok profile links; export CSV
- Let users plug in their own Apify token and LLM key from the UI; run a key-free demo on bundled snapshot data
### OUT — what it does NOT do (deliberate decisions)
- Real audience demographics — TikTok does not expose them publicly; audience fit is LLM-estimated and labeled as such
- Scraping that needs a logged-in account, or any private data
- Contacting creators / outreach, rate cards, campaign tracking
- Multi-user accounts and cloud hosting — runs locally via docker compose
- Platforms other than TikTok as KOL source (Instagram/YouTube = LATER)

## Features (= requirements — one row per feature + AC; tag MUST/LATER)
| ID | Tag | Feature | Passes when (AC) |
|---|---|---|---|
| F1 | MUST | Brand analysis: website crawl (Crawl4AI) + FB page/posts (Apify) → LLM Brand Profile | For a test brand, profile JSON has every field filled and is shown in UI |
| F2 | MUST | FB page discovery + confirm: social links found on the website are listed with title, location, followers, last post date; user picks one or pastes a URL | A foreign/stale franchise page is visibly distinguishable from the main page |
| F3 | MUST | KOL discovery: LLM-proposed Thai hashtags/keywords → Apify TikTok hashtag search → dedupe creators → hard filters, each toggleable in UI with editable threshold: Thai captions ≥60% (`textLanguage=th`), exclude private accounts, last post ≤30 days, follower range (default ≥10K) | Turning a filter off/on changes the candidate list; count dropped per filter is shown |
| F4 | MUST | Enrichment: latest N videos per shortlisted creator → median views, median ER (by views), posting frequency, last post date, ad / TikTok Shop share | Metrics computed from recent videos, not lifetime totals |
| F5 | MUST | Scoring + ranking, 4 axes 0–100: Relevance 40% (LLM rubric: category, style/tone, product fit, brand safety + reason), Engagement 25% (median ER by views as percentile within follower tier + views/followers), Audience fit 20% (LLM-estimated audience vs brand target, labeled "estimated" + confidence), Activity & authenticity 15% (posting cadence, view consistency, ad/sponsored share, followers-vs-views anomaly) → weighted total; weights shown and adjustable in UI | UI shows the scoring criteria + weights, and per creator: 4 sub-scores, total, reason and which values are estimated |
| F6 | MUST | Results UI: ranked list with TikTok profile link, avatar, followers, metrics, scores, reasons; CSV export | Every row links to a working `tiktok.com/@user` profile |
| F7 | MUST | Settings: Apify token + LLM provider picker (OpenRouter / Anthropic / OpenAI-compatible custom: base URL, key, model) set from UI with Test button (Apify shows plan + remaining credit); keys encrypted at rest, never returned in full; fallback to `credential/.env` | App runs end-to-end with keys entered only in the UI |
| F8 | MUST | Demo mode: full flow on a bundled snapshot with no keys | Fresh clone + `docker compose up` shows a ranked list without any key |
| F9 | MUST | Cost control: estimated Apify cost before each run, lean/full budget presets, cache of Apify results | Re-running the same brand costs $0 Apify |
| F10 | MUST | Privacy: keep only public, business-relevant fields; mask phone numbers/emails found in creator bios; delete-run button | No phone number from a creator bio is stored or displayed |
| F11 | MUST | Pipeline progress: background job with step-by-step status in UI | User sees which step is running and any step error |
| F12 | MUST | "Connect with OpenRouter" (OAuth PKCE) in Settings, alongside API-key paste | Clicking Connect → OpenRouter login → returns to app with a working key, no copy-paste |
| F13 | LATER | Past collaborations from FB `paidPartnership`/`collaborators` → lookalike KOLs | — |
| F14 | LATER | Comment sampling to strengthen audience estimation | — |
| F15 | LATER | Instagram / YouTube creators | — |

## User Flow (main flow only)
- Marketer → New analysis → enters website URL (+ optional FB URL) → confirms FB page → sees Brand Profile (editable hashtags) → sees cost estimate → Run → watches progress → gets ranked KOL list → exports CSV
- First-time user → Settings → pastes Apify token + LLM key → Test → ready (or uses Demo mode)

## Definition of Done
- [ ] All MUST features pass their AC on at least one real Thai brand
- [ ] Demo mode works from a fresh clone with no keys
- [ ] README: quick start ≤3 commands, how it works, limitations, ethics & privacy, citations, AI disclosure
- [ ] Loom 5–10 min recorded (demo + technical decisions + business impact + future work)
- [ ] Source pushed to GitHub, commit history readable as a story

## Techstack / Architecture
| Layer | What | Why |
|---|---|---|
| Frontend | Next.js (App Router) + TypeScript + Tailwind CSS + shadcn/ui | Product-grade UI fast; owner's preferred stack |
| UI design | Convert Cake-style look: white background, royal-blue accent (own SmartKOL name/logo, not Convert Cake's); English UI, Thai data; step wizard (Brand input → Brand Profile review + cost → live progress → results); results = sortable table + detail drawer | Matches the agency's brand; table compares 10 creators best; wizard mirrors the pipeline |
| Backend | Python + FastAPI | Best scraping/AI library ecosystem; async background jobs |
| Website extraction | Crawl4AI (Playwright, Apache-2.0) | Renders JS sites, outputs LLM-ready markdown; spike: 5 pages in seconds, found social links |
| FB + TikTok data | Apify Actors: `apify/facebook-pages-scraper`, `apify/facebook-posts-scraper`, `clockworks/tiktok-scraper` via `apify-client` | No official API path is open (Graph API needs App Review; TikTok APIs are partner/research-only) |
| LLM | Thin adapter: Anthropic Messages API + OpenAI-compatible API; default OpenRouter `anthropic/claude-haiku-5.5` | User picks provider/key; covers Claude, OpenAI, OpenRouter, Z.ai, Gemini, Ollama; Haiku 5.5 on OpenRouter = $0.10/M in, $0.50/M out (2026-10-29) |
| Matching | LLM-as-judge for relevance/audience + deterministic metrics (median ER by views, tier percentiles) | Small candidate pool (~30–80) → judge is more accurate and explainable than embeddings |
| Data / Storage | SQLite (runs, cache, encrypted settings via `cryptography` Fernet) | Zero-ops, single file |
| Deploy | Local `docker compose` (frontend + backend) | One command on any machine |
| Environment constraints | Apify free plan = $5/month; spike measured ≈ $0.30–0.45 per full analysis | Cost control is a feature (F9) |

### Pipeline
`URL → crawl website + scrape FB → LLM Brand Profile → hashtags → TikTok hashtag search → Thai filter + dedupe → shortlist → enrich recent videos → score (LLM + metrics) → rank → UI / CSV`

## Project documents (status always lives in SSOT.md — no duplication)
| File | Role |
|---|---|
| README.md | how to run (for humans) |
| SSOT.md | current status (local only, not tracked) |
| AGENTS.md | working rules for AI agents |

## Project owner preferences (binding for all work in this project)
- Commits carry the owner's name only — no AI trailers; AI usage disclosed in README
- Docs and commit messages read as a normal product — no references to an assessment audience
- SSOT.md and spike/ stay local (git-ignored) for now
- No hardcoded account: every external service must be configurable by the user (UI or `credential/.env`)
