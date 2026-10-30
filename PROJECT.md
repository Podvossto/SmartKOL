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
| F1 | MUST | Brand analysis from a website, a Facebook page, or both (read together): website via Playwright, Facebook page + recent posts via Apify → LLM brand brief (positioning, audience persona, voice with do/don't, content pillars with how each performs, ideal-creator criteria, evidence by source, what was not found) with a combined summary plus a separate summary per source; the ideal-creator criteria and the TikTok hashtags can be edited by the user before searching, and edited sections are marked | With both inputs the profile shows Combined / Website / Facebook views; with one input only that source's view exists; every profile field is filled |
| F2 | MUST | Link check before anything paid: each link must be reachable (site responds, Facebook page exists, no private-network targets). Website-only input reads only the website (free) unless the user asks us to find its Facebook page, in which case it lists the Facebook pages the site links to (title, location, followers, last post) for the user to confirm, paste another, or skip | A dead, missing or private link is rejected next to its field and costs $0; a foreign or inactive page is flagged |
| F3 | MUST | KOL discovery: LLM-proposed Thai hashtags/keywords → Apify TikTok hashtag search → dedupe creators → hard filters, each toggleable in UI with editable threshold: Thai captions ≥60% (`textLanguage=th`), exclude private accounts, last post ≤30 days, follower range (default ≥10K) | Turning a filter off/on changes the candidate list; count dropped per filter is shown |
| F4 | MUST | Enrichment: latest N videos per shortlisted creator → median views, median ER (by views), posting frequency, last post date, ad / TikTok Shop share | Metrics computed from recent videos, not lifetime totals |
| F5 | MUST | Scoring + ranking, 4 axes 0–100: Relevance 40% (LLM rubric: category, style/tone, product fit, brand safety + reason), Engagement 25% (median ER by views as percentile within follower tier + views/followers), Audience fit 20% (LLM-estimated audience vs brand target, labeled "estimated" + confidence), Activity & authenticity 15% (posting cadence, view consistency, ad/sponsored share, followers-vs-views anomaly) → weighted total; weights shown and adjustable in UI | UI shows the scoring criteria + weights, and per creator: 4 sub-scores, total, reason and which values are estimated |
| F6 | MUST | Results UI: ranked list with TikTok profile link, avatar, followers, metrics, scores, reasons; CSV export | Every row links to a working `tiktok.com/@user` profile |
| F7 | MUST | Settings: Apify token + LLM provider picker (OpenRouter / Anthropic / OpenAI-compatible custom: base URL, key, model) set from UI with Test button (Apify shows plan + remaining credit); keys encrypted at rest, never returned in full; fallback to `credential/.env` | App runs end-to-end with keys entered only in the UI |
| F8 | MUST | Demo mode: full flow on a bundled snapshot with no keys | Fresh clone + `docker compose up` shows a ranked list without any key |
| F9 | MUST | Cost control: estimated Apify cost before each run, lean/full budget presets, cache of Apify results | Re-running the same brand costs $0 Apify |
| F10 | MUST | Privacy: keep only public, business-relevant fields; mask phone numbers/emails found in creator bios; delete-run button | No phone number from a creator bio is stored or displayed |
| F11 | MUST | Pipeline progress: background job with step-by-step status in UI | User sees which step is running and any step error |
| F16 | MUST | Analysis workspace: one page per step (Brand/Profile → Creators → Results) driven by a single step list, brand logo, cover banner and sample pictures from Facebook/website (fetched and stored server-side, never loaded from the source by the browser), recent analyses on the home page with delete | Reopening a past analysis costs $0; deleting removes the analysis and its logo; adding a step needs one config row and one page |
| F17 | MUST | Transparency: every block is labelled as read from a source or written by the AI (model named); Apify credits used and left are shown with each analysis; a cost estimate is shown before every run; a website and Facebook page that don't appear to belong together raise a warning | Each profile block carries a label; the form shows the estimate and remaining credits before Analyze; mismatched links produce a warning that names the other site |
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
| Website extraction | Playwright (headless Chromium), own text extractor | Renders JS sites with no third-party service or extra crawler dependency; skips nav/footer, images and fonts; also used to verify Facebook links for free |
| FB + TikTok data | Apify Actors: `apify/facebook-pages-scraper`, `apify/facebook-posts-scraper`, `clockworks/tiktok-scraper` via `apify-client` | No official API path is open (Graph API needs App Review; TikTok APIs are partner/research-only) |
| LLM | Thin adapter: Anthropic Messages API + OpenAI-compatible API; default OpenRouter `anthropic/claude-haiku-5.5` | User picks provider/key; covers Claude, OpenAI, OpenRouter, Z.ai, Gemini, Ollama; Haiku 5.5 on OpenRouter = $0.10/M in, $0.50/M out (2026-10-29) |
| Matching | LLM-as-judge for relevance/audience + deterministic metrics (median ER by views, tier percentiles) | Small candidate pool (~30–80) → judge is more accurate and explainable than embeddings |
| Data / Storage | SQLite (runs, cache, encrypted settings via `cryptography` Fernet) | Zero-ops, single file |
| Deploy | Local `docker compose` (frontend + backend) | One command on any machine |
| Environment constraints | Apify free plan = $5/month; measured: brand analysis $0.096 (cold) / $0 (cached) + model ≈ $0.003; Apify prices: Facebook page $0.012, post $0.005, TikTok result $0.0037 | Cost control is a feature (F9) |

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
